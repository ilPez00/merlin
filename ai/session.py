"""
MerlinSession — manages the ongoing AI conversation.
Receives batched sensor context from StreamProcessor and maintains
a rolling conversation. Uses the agentic loop for queries.
"""

import asyncio
import logging
import os
from pathlib import Path

from . import agent as agent_module

log = logging.getLogger("merlin.session")

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"
MAX_HISTORY = 30  # max messages to keep (older ones are trimmed)


def _build_backend():
    """
    Select and return the appropriate backend based on environment variables.

    Priority:
    1. MERLIN_BACKEND=anthropic  → AnthropicBackend
    2. ANTHROPIC_API_KEY set     → AnthropicBackend
    3. Otherwise                 → OpenAICompatBackend (DeepSeek, OpenAI, local)
    """
    backend_name = os.environ.get("MERLIN_BACKEND", "").lower()
    if backend_name == "anthropic" or (
        not backend_name and os.environ.get("ANTHROPIC_API_KEY")
    ):
        from .backends.anthropic_backend import AnthropicBackend
        return AnthropicBackend()
    else:
        from .backends.openai_compat import OpenAICompatBackend
        return OpenAICompatBackend()


class MerlinSession:
    def __init__(self):
        self._backend = None
        self._history: list[dict] = []
        self._system_prompt: str = ""
        self._lock = asyncio.Lock()

    async def start(self):
        self._backend = _build_backend()
        await self._backend.start()
        self._system_prompt = SYSTEM_PROMPT_PATH.read_text()
        # Share backend reference with tools for translation
        from .tools import set_latest_backend
        set_latest_backend(self._backend)
        log.info("AI session started (model: %s)", self._backend.model())

    def model(self) -> str:
        return self._backend.model() if self._backend else "unknown"

    # ── Context accumulation ──────────────────────────────────────────────────

    async def push_context(
        self,
        text: str = "",
        frame_b64: str | None = None,
        mode: str = "",
    ):
        """
        Called by StreamProcessor with batched sensor data.
        Appends a user message to the history without calling the LLM.
        """
        async with self._lock:
            content = []

            if frame_b64:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame_b64}",
                        "detail": "low",
                    },
                })

            ctx_text = f"[mode: {mode}]\n{text}" if mode and text else text
            if ctx_text:
                content.append({"type": "text", "text": ctx_text})

            if content:
                self._history.append({
                    "role": "user",
                    "content": content if len(content) > 1 else content[0]["text"] if content[0]["type"] == "text" else content,
                })
                log.info("context pushed (%d chars, frame=%s, mode=%s)",
                         len(text), frame_b64 is not None, mode)
                self._trim_history()

    # ── Query (agentic) ───────────────────────────────────────────────────────

    async def query(self, question: str, mode: str = "QUERY") -> str:
        """
        Explicit query — runs the agentic tool-use loop and returns the answer.
        Updates conversation history with the final Q&A pair.
        """
        async with self._lock:
            answer = await agent_module.run(
                backend=self._backend,
                system_prompt=self._system_prompt,
                history=self._history,
                query=question,
                mode=mode,
            )
            # Append the Q&A to history (simple form, no tool calls)
            self._history.append({"role": "user", "content": question})
            self._history.append({"role": "assistant", "content": answer})
            self._trim_history()
            log.info("query answered (%d history msgs)", len(self._history))
            return answer

    # ── Auto-observe ──────────────────────────────────────────────────────────

    async def auto_observe(self, mode: str = "SCOUT") -> str | None:
        """
        Proactive observation — the model comments on recent context.
        No tool use; short response.
        """
        async with self._lock:
            if not self._history:
                return None

            # Brief prompt — no tools, low token budget
            observe_prompt = (
                "Based on everything you've observed so far, "
                "give a brief (1-3 sentence) observation or insight relevant to "
                f"{mode} mode. Only speak if you have something genuinely useful."
            )

            response = await self._backend.complete(
                messages=list(self._history) + [
                    {"role": "user", "content": observe_prompt}
                ],
                tools=None,
                system=self._system_prompt,
                max_tokens=200,
            )

            observation = response.text or ""
            if observation:
                self._history.append({"role": "assistant", "content": observation})
                self._trim_history()
            return observation or None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _trim_history(self):
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]
