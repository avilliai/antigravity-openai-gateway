# -*- coding: utf-8 -*-
"""OpenAI-compatible API Protocols & Data Models.

Defines Pydantic schemas for standard OpenAI v1 chat completion requests,
streaming chunks, model metadata, and prompt formatters.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = "gemini-3.8-flash-low"
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChunkChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChunkChoice]


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "google-antigravity"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelCard]


def format_messages_for_antigravity(messages: List[ChatMessage]) -> tuple[str, Optional[str]]:
    """Convert OpenAI message list into a unified prompt and optional system instructions.

    Returns:
        (latest_prompt_with_history, system_instructions)
    """
    system_parts: List[str] = []
    history_turns: List[str] = []
    latest_user_content: str = ""

    for i, msg in enumerate(messages):
        role = msg.role.lower()
        content_str = msg.content if isinstance(msg.content, str) else str(msg.content)

        if role == "system":
            system_parts.append(content_str)
        elif role in ("user", "human"):
            if i == len(messages) - 1:
                latest_user_content = content_str
            else:
                prefix = f"User ({msg.name})" if msg.name else "User"
                history_turns.append(f"{prefix}: {content_str}")
        elif role in ("assistant", "bot", "model"):
            prefix = f"Assistant ({msg.name})" if msg.name else "Assistant"
            history_turns.append(f"{prefix}: {content_str}")

    sys_instructions = "\n\n".join(system_parts).strip() if system_parts else None

    prompt_builder: List[str] = []
    if history_turns:
        prompt_builder.append("【历史上下文对话】")
        prompt_builder.append("\n".join(history_turns[-10:]))  # Keep recent history
        prompt_builder.append("\n")

    if latest_user_content:
        prompt_builder.append(latest_user_content)
    elif messages:
        # Fallback if last message was not user role
        last_content = messages[-1].content
        prompt_builder.append(last_content if isinstance(last_content, str) else str(last_content))
    else:
        prompt_builder.append("Hello")

    return "\n".join(prompt_builder).strip(), sys_instructions
