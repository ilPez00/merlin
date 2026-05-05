"""
Merlin — Agentic loop
Runs a tool-use loop until the model produces a final text response.
Backend-agnostic: works with OpenAI-compat or Anthropic backends.
Messages are kept in OpenAI format; each backend translates as needed.
"""

import json
import logging
from typing import Any

from .tools import TOOL_DEFINITIONS, call_tool

log = logging.getLogger("merlin.agent")

MAX_TOOL_ROUNDS = 10  # Safety: stop after this many consecutive tool rounds


async def run(
    backend: Any,
    system_prompt: str,
    history: list[dict],
    query: str,
    frame_b64: str | None = None,
    mode: str = "QUERY",
    max_tokens: int = 1024,
) -> str:
    """
    Run the agentic tool-use loop.

    Parameters
    ----------
    backend      : OpenAICompatBackend | AnthropicBackend
    system_prompt: Full system prompt text
    history      : Rolling conversation history (read-only; do not mutate)
    query        : The user's question / trigger text
    frame_b64    : Optional base64 JPEG camera frame
    mode         : Current HUD mode (included in context)
    max_tokens   : Max tokens for each LLM call

    Returns
    -------
    Final text response from the model.
    """
    # Build the initial user message for this turn
    user_msg = {
        "role": "user",
        "content": _build_user_content(query, frame_b64, mode),
    }

    # Local messages: history + this query (never modifies caller's history list)
    messages = list(history) + [user_msg]

    for round_num in range(MAX_TOOL_ROUNDS):
        log.debug("agent round %d, messages=%d", round_num + 1, len(messages))

        response = await backend.complete(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            system=system_prompt,
            max_tokens=max_tokens,
        )

        if not response.tool_calls:
            # Model produced a final text answer — we're done
            log.info("agent finished in %d round(s)", round_num + 1)
            return response.text or ""

        # ── Tool-call round ───────────────────────────────────────────────────
        log.info("agent round %d: %d tool call(s)", round_num + 1, len(response.tool_calls))

        # 1. Append the assistant message with tool_calls (OpenAI format)
        messages.append({
            "role": "assistant",
            "content": response.text,  # may be None
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ],
        })

        # 2. Execute each tool call and append results
        for tc in response.tool_calls:
            log.info("calling tool %s(%s)", tc.name, _summarise_args(tc.arguments))
            result = await call_tool(tc.name, tc.arguments)
            log.debug("tool %s result: %s…", tc.name, result[:120])
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": result,
            })

    # Fell through MAX_TOOL_ROUNDS — ask for a final answer without tools
    log.warning("agent hit MAX_TOOL_ROUNDS=%d; requesting final answer", MAX_TOOL_ROUNDS)
    messages.append({
        "role": "user",
        "content": "Please give a final answer based on everything gathered so far.",
    })
    response = await backend.complete(
        messages=messages,
        tools=None,
        system=system_prompt,
        max_tokens=max_tokens,
    )
    return response.text or "(no response)"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_user_content(query: str, frame_b64: str | None, mode: str):
    text = f"[mode: {mode}]\n{query}" if mode else query

    if frame_b64:
        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{frame_b64}",
                    "detail": "low",
                },
            },
            {"type": "text", "text": text},
        ]

    return text


def _summarise_args(args: dict) -> str:
    s = json.dumps(args)
    return s[:80] + "…" if len(s) > 80 else s
