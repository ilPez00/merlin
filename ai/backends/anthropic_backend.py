"""
Anthropic (Claude) backend.
Uses the anthropic SDK and translates to the shared ChatResponse format.
"""

import json
import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("merlin.backend.anthropic")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


def _openai_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-style tool definitions to Anthropic format."""
    result = []
    for t in tools:
        fn = t.get("function", {})
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _openai_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """
    Convert messages from OpenAI format to Anthropic format.
    Anthropic doesn't accept 'system' in messages — that's handled separately.
    Also converts tool result messages.
    """
    out = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            # system is passed separately to client.messages.create()
            continue

        if role == "tool":
            # OpenAI tool result → Anthropic tool_result block
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": content if isinstance(content, str) else json.dumps(content),
                }],
            })
            continue

        if role == "assistant" and "tool_calls" in msg:
            # OpenAI-style assistant message with tool_calls → Anthropic tool_use blocks
            blocks = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                try:
                    args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                except (json.JSONDecodeError, TypeError):
                    args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": fn["name"],
                    "input": args,
                })
            out.append({"role": "assistant", "content": blocks})
            continue

        if role == "assistant" and isinstance(content, list):
            # Already in Anthropic format
            out.append({"role": "assistant", "content": content})
            continue

        # Standard text message
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            # OpenAI multimodal content (image_url + text)
            anth_content = []
            for item in content:
                if item.get("type") == "text":
                    anth_content.append({"type": "text", "text": item["text"]})
                elif item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    if url.startswith("data:"):
                        # data:image/jpeg;base64,<b64>
                        media_part, b64 = url.split(",", 1)
                        media_type = media_part.split(":")[1].split(";")[0]
                        anth_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        })
            out.append({"role": role, "content": anth_content})
        else:
            out.append({"role": role, "content": str(content)})

    return out


class AnthropicBackend:
    def __init__(self):
        self._client = None

    async def start(self):
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MERLIN_API_KEY")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        log.info("Anthropic backend ready")

    def model(self) -> str:
        return os.environ.get("MERLIN_MODEL", "claude-opus-4-6")

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str = "",
        max_tokens: int = 1024,
    ) -> ChatResponse:
        anth_messages = _openai_messages_to_anthropic(messages)
        kwargs = {
            "model": self.model(),
            "max_tokens": max_tokens,
            "messages": anth_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _openai_tools_to_anthropic(tools)

        resp = await self._client.messages.create(**kwargs)

        text = None
        tool_calls = []

        for block in resp.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        return ChatResponse(text=text, tool_calls=tool_calls)
