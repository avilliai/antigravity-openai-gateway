# -*- coding: utf-8 -*-
"""Unit and Integration Tests for Antigravity OpenAI Gateway."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from agy_gateway.config import GatewayConfig
from agy_gateway.protocol import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    format_messages_for_antigravity,
)
from agy_gateway.server import create_app


class TestProtocol(unittest.TestCase):
    """Test OpenAI protocol conversions and prompt formatting."""

    def test_message_formatting_single(self):
        messages = [ChatMessage(role="user", content="Hello Antigravity!")]
        prompt, sys_inst = format_messages_for_antigravity(messages)
        self.assertEqual(prompt, "Hello Antigravity!")
        self.assertIsNone(sys_inst)

    def test_message_formatting_with_system_and_history(self):
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="What is 1+1?"),
            ChatMessage(role="assistant", content="It is 2."),
            ChatMessage(role="user", content="And + 1?"),
        ]
        prompt, sys_inst = format_messages_for_antigravity(messages)
        self.assertEqual(sys_inst, "You are a helpful assistant.")
        self.assertIn("【历史上下文对话】", prompt)
        self.assertIn("User: What is 1+1?", prompt)
        self.assertIn("Assistant: It is 2.", prompt)
        self.assertTrue(prompt.endswith("And + 1?"))


class TestConfig(unittest.TestCase):
    """Test configuration loading and model resolution."""

    def test_model_alias_resolution(self):
        cfg = GatewayConfig()
        self.assertEqual(cfg.model_aliases.get("gpt-4o"), "gemini-3.8-flash-medium")
        self.assertEqual(cfg.model_aliases.get("gpt-3.5-turbo"), "gemini-3.8-flash-low")
        self.assertEqual(cfg.model_aliases.get("claude-3-5-sonnet"), "claude-sonnet-4-6")


class TestApiRoutes(unittest.TestCase):
    """Test FastAPI OpenAI endpoint responses."""

    def setUp(self):
        self.cfg = GatewayConfig(api_key="test-secret-key")
        self.app = create_app(self.cfg)
        self.client = TestClient(self.app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "antigravity-openai-gateway")

    def test_models_endpoint_auth_required(self):
        # Without key -> 401
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 401)

        # With key -> 200
        response = self.client.get(
            "/v1/models", headers={"Authorization": "Bearer test-secret-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object"], "list")
        model_ids = [m["id"] for m in data["data"]]
        self.assertIn("gpt-4o", model_ids)
        self.assertIn("gemini-3.8-flash-low", model_ids)

    @patch("agy_gateway.agy_executor.AgyExecutor.execute_chat")
    def test_chat_completions_non_streaming(self, mock_execute_chat):
        from agy_gateway.protocol import ChatChoice, ChoiceMessage, UsageInfo

        mock_execute_chat.return_value = ChatCompletionResponse(
            id="chatcmpl-test12345",
            model="gpt-4o",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content="Hello from mock!"),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(prompt_tokens=5, completion_tokens=4, total_tokens=9),
        )

        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
        }
        response = self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer test-secret-key"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object"], "chat.completion")
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello from mock!")

    @patch("agy_gateway.agy_executor.AgyExecutor.execute_stream")
    def test_chat_completions_streaming(self, mock_execute_stream):
        async def fake_stream(_):
            yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":""},"index":0}]}\n\n'
            yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hi"},"index":0}]}\n\n'
            yield 'data: [DONE]\n\n'

        mock_execute_stream.return_value = fake_stream(None)

        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }
        response = self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer test-secret-key"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        text = response.text
        self.assertIn("data: [DONE]", text)
        self.assertIn('"content":"Hi"', text)


if __name__ == "__main__":
    unittest.main()
