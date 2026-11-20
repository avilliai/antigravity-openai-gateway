# -*- coding: utf-8 -*-
"""Live Integration Test for AgyExecutor with installed agy.exe."""

import asyncio
import unittest

from agy_gateway.agy_executor import AgyExecutor
from agy_gateway.config import GatewayConfig
from agy_gateway.protocol import ChatMessage, ChatCompletionRequest


class TestLiveAgyExecutor(unittest.IsolatedAsyncioTestCase):
    """Test actual execution against installed Antigravity CLI."""

    async def test_live_chat_query(self):
        cfg = GatewayConfig.load()
        executor = AgyExecutor(cfg)

        request = ChatCompletionRequest(
            model="gemini-3.8-flash-low",
            messages=[
                ChatMessage(role="user", content="Respond with the exact word 'PONG' and nothing else.")
            ],
            stream=False,
        )

        response = await executor.execute_chat(request)
        self.assertIsNotNone(response)
        self.assertTrue(response.id.startswith("chatcmpl-"))
        self.assertTrue(len(response.choices) > 0)
        content = response.choices[0].message.content.strip()
        print(f"\n[Live agy response]: {content}")
        self.assertIn("PONG", content.upper())

    async def test_live_chat_streaming(self):
        cfg = GatewayConfig.load()
        executor = AgyExecutor(cfg)

        request = ChatCompletionRequest(
            model="gemini-3.8-flash-low",
            messages=[
                ChatMessage(role="user", content="Count from 1 to 3, one number per line.")
            ],
            stream=True,
        )

        chunks = []
        async for sse_chunk in executor.execute_stream(request):
            chunks.append(sse_chunk)

        self.assertTrue(len(chunks) >= 2)
        full_text = "".join(chunks)
        print(f"\n[Live agy streaming chunks count]: {len(chunks)}")
        self.assertIn("data: [DONE]", full_text)


if __name__ == "__main__":
    unittest.main()
