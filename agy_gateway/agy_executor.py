# -*- coding: utf-8 -*-
"""Antigravity CLI Subprocess Executor.

Manages subprocess execution of the Google Antigravity `agy` CLI binary,
handling concurrency, proxy routing, retry mechanisms, non-streaming and SSE streaming
responses compatible with OpenAI chat completion standards.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from agy_gateway.config import GatewayConfig
from agy_gateway.protocol import (
    ChatChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceMessage,
    ChunkChoice,
    DeltaMessage,
    UsageInfo,
    format_messages_for_antigravity,
)

logger = logging.getLogger("agy_gateway.executor")

# Project root directory used as clean isolated workspace for agy execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AgyExecutor:
    """Subprocess executor for Antigravity CLI."""

    def __init__(self, config: GatewayConfig, workspace_dir: Optional[Path] = None):
        self.config = config
        self.workspace_dir = workspace_dir or PROJECT_ROOT
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    def _get_subprocess_env(self) -> dict[str, str]:
        """Inject proxy variables if configured."""
        env = os.environ.copy()
        if self.config.proxy:
            env["HTTP_PROXY"] = self.config.proxy
            env["HTTPS_PROXY"] = self.config.proxy
            env["ALL_PROXY"] = self.config.proxy
            env["http_proxy"] = self.config.proxy
            env["https_proxy"] = self.config.proxy
            env["all_proxy"] = self.config.proxy
        return env

    def _resolve_model(self, requested_model: str) -> str:
        """Map client model name (e.g. gpt-4o) to official Antigravity model name."""
        return self.config.model_aliases.get(requested_model, requested_model or self.config.default_model)

    def _build_full_prompt(self, request: ChatCompletionRequest) -> str:
        """Format request messages into unified prompt text."""
        prompt, sys_instructions = format_messages_for_antigravity(request.messages)
        if sys_instructions:
            return f"[System Instructions: {sys_instructions}]\n\n{prompt}"
        return prompt

    def _build_command(
        self, full_prompt: str, model_name: str, output_format: str = "text"
    ) -> list[str]:
        """Build agy CLI command line arguments."""
        cmd = [
            self.config.cli_command,
            "-p", full_prompt,
            "--dangerously-skip-permissions",
            "--output-format", output_format,
        ]
        if model_name:
            cmd.extend(["--model", model_name])
        return cmd

    async def execute_chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute chat turn and return standard ChatCompletionResponse."""
        model_name = self._resolve_model(request.model)
        full_prompt = self._build_full_prompt(request)
        cmd = self._build_command(full_prompt, model_name, output_format="text")

        async with self._semaphore:
            output_text = await self._run_subprocess_with_retry(cmd)

        cmpl_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        prompt_tokens = max(1, len(full_prompt) // 4)
        completion_tokens = max(1, len(output_text) // 4)
        total_tokens = prompt_tokens + completion_tokens

        return ChatCompletionResponse(
            id=cmpl_id,
            model=request.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content=output_text),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

    async def execute_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[str, None]:
        """Execute chat turn and yield SSE formatted data chunks."""
        model_name = self._resolve_model(request.model)
        full_prompt = self._build_full_prompt(request)
        cmd = self._build_command(full_prompt, model_name, output_format="text")

        cmpl_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        # First chunk with assistant role
        first_chunk = ChatCompletionChunk(
            id=cmpl_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=""),
                    finish_reason=None,
                )
            ],
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        async with self._semaphore:
            async for piece in self._run_streaming_subprocess(cmd):
                if piece:
                    chunk = ChatCompletionChunk(
                        id=cmpl_id,
                        created=created,
                        model=request.model,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=DeltaMessage(content=piece),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

        # Final stop chunk
        stop_chunk = ChatCompletionChunk(
            id=cmpl_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=DeltaMessage(),
                    finish_reason="stop",
                )
            ],
        )
        yield f"data: {stop_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    async def _run_subprocess_with_retry(self, cmd: list[str]) -> str:
        """Run agy subprocess with automatic retry on transient network errors."""
        env = self._get_subprocess_env()
        for attempt in range(2):
            try:
                logger.info(f"Subprocess executing: {' '.join(cmd[:6])} (attempt {attempt + 1})")
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace_dir),
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.config.timeout
                )
                out_str = stdout.decode("utf-8", errors="replace").strip()
                err_str = stderr.decode("utf-8", errors="replace").strip()

                if proc.returncode == 0 and out_str:
                    return out_str

                is_transient = (
                    "EOF" in err_str
                    or "connection" in err_str.lower()
                    or "context deadline" in err_str.lower()
                    or "empty conversation id" in err_str.lower()
                    or "empty conversation id" in out_str.lower()
                )
                if attempt == 0 and is_transient:
                    logger.warning(f"Transient error ({err_str or out_str}), retrying in 1.5s...")
                    await asyncio.sleep(1.5)
                    continue

                if proc.returncode == 0 and out_str:
                    return out_str

                error_msg = err_str or f"Antigravity CLI failed with exit code {proc.returncode}"
                raise RuntimeError(error_msg)

            except asyncio.TimeoutError:
                if attempt == 0:
                    logger.warning("Subprocess timed out, retrying once...")
                    continue
                raise RuntimeError(f"Antigravity CLI timed out after {self.config.timeout}s")

        raise RuntimeError("Subprocess execution failed after retries")

    async def _run_streaming_subprocess(self, cmd: list[str]) -> AsyncGenerator[str, None]:
        """Stream output from agy CLI stdout in real time chunks."""
        env = self._get_subprocess_env()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace_dir),
            env=env,
        )

        buffer = bytearray()
        chunk_size = self.config.stream_chunk_size * 4

        while True:
            chunk = await proc.stdout.read(64)
            if not chunk:
                break
            buffer.extend(chunk)
            try:
                text = buffer.decode("utf-8")
                buffer.clear()
                yield text
            except UnicodeDecodeError:
                if len(buffer) > 256:
                    text = buffer.decode("utf-8", errors="replace")
                    buffer.clear()
                    yield text

        if buffer:
            yield buffer.decode("utf-8", errors="replace")

        await proc.wait()
