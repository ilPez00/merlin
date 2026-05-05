"""
OpenAI-compatible backend — works with OpenAI, DeepSeek, or any
server that implements the OpenAI chat-completions API.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("merlin.backend.openai")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class OpenAICompatBackend:
    def __init__(self):
        self._client = None

    async def start(self):
        from openai import AsyncOpenAI

        api_key = (
            os.environ.get("MERLIN_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or "sk-placeholder"
        )
        base_url = os.environ.get("MERLIN_BASE_URL") or None  # None = default OpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        log.info("OpenAI-compat backend ready (base_url=%s)", base_url or "default")

    def model(self) -> str:
        return os.environ.get("MERLIN_MODEL", "deepseek-chat")

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str = "",
        max_tokens: int = 1024,
    ) -> ChatResponse:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self.model(),
            "messages": full_messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = await self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return ChatResponse(text=msg.content, tool_calls=tool_calls)
