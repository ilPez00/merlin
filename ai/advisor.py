"""Proactive advisor — periodically analyzes user data and pushes useful tips."""

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("merlin.advisor")

CONV_PATH = Path.home() / ".merlin" / "conversations.md"
DATA_DIR = Path.home() / ".merlin" / "data"


class Advisor:
    """Background advisor that suggests useful actions based on user data.

    Runs every N minutes and asks the LLM to generate a brief,
    personalized tip based on the user's recent activity.
    """

    def __init__(self):
        self._last_advice_time = 0
        self._interval = 1800  # 30 min default
        self._callback = None  # function(msg) called with tip text

    def set_callback(self, fn):
        self._callback = fn

    def set_interval(self, seconds: int):
        self._interval = seconds

    async def tick(self):
        """Called periodically. Generates advice if enough time has passed."""
        now = time.time()
        if now - self._last_advice_time < self._interval:
            return
        self._last_advice_time = now

        tip = await self._generate_tip()
        if tip and self._callback:
            self._callback(tip)

    async def _generate_tip(self) -> str | None:
        """Ask the LLM for a brief useful observation based on stored data."""
        context = self._build_context()
        if not context:
            return None

        from ai.session import MerlinSession

        session = MerlinSession()
        await session.start()

        prompt = (
            "You are Merlin, a proactive AI assistant. Based on the user's recent data below, "
            "give ONE brief, specific, useful suggestion or observation. "
            "Be concise (1-3 sentences). Do NOT greet. Do NOT ask how you can help. "
            "Just state the tip directly. Examples:\n"
            "- 'You've spent €45 on coffee this week. Making it at home saves ~€30.'\n"
            "- 'You logged 3 pushup sessions this week. Adding 1 more hits your goal.'\n"
            "- 'You seem tired (68%) and have a meeting in 30 min. Take a quick walk first.'\n"
            "- 'You haven't logged a meal today. Did you eat breakfast?'\n"
            "- 'It's 3pm — your energy dip time. A short break now boosts focus.'\n"
            "If nothing useful to say, respond with exactly: PASS"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Recent data:\n{context[:2000]}"},
        ]

        try:
            response = await session._backend.complete(
                messages=messages,
                tools=None,
                system=prompt,
                max_tokens=200,
                temperature=0.5,
            )
            text = (response.text or "").strip()
            if text == "PASS" or len(text) < 10:
                return None
            return text
        except Exception as e:
            log.debug("advisor generation error: %s", e)
            return None

    def _build_context(self) -> str:
        """Gather recent data from conversations, diary, and tools."""
        parts = []

        # Last few conversation exchanges
        if CONV_PATH.exists():
            try:
                text = CONV_PATH.read_text(encoding="utf-8")
                lines = text.strip().split("\n")
                parts.append("[recent conversations]")
                parts.append("\n".join(lines[-20:]))
            except Exception:
                pass

        # Todo status
        todos_file = DATA_DIR / "todos.json"
        if todos_file.exists():
            try:
                import json
                todos = json.loads(todos_file.read_text())
                if todos:
                    done = sum(1 for t in todos if t.get("done"))
                    total = len(todos)
                    pending = [t for t in todos if not t.get("done")]
                    parts.append(f"[todos] {done}/{total} done")
                    if pending:
                        parts.append("pending: " + ", ".join(t.get("text", "")[:30] for t in pending[:3]))
            except Exception:
                pass

        # Expenses today
        expenses_file = DATA_DIR / "expenses.json"
        if expenses_file.exists():
            try:
                import json
                exps = json.loads(expenses_file.read_text())
                today = time.strftime("%Y-%m-%d")
                today_exps = [e for e in exps if e.get("date") == today]
                if today_exps:
                    total = sum(e.get("amount", 0) for e in today_exps)
                    parts.append(f"[spent today] €{total:.2f}")
            except Exception:
                pass

        # Tiredness
        from ai.widgets import estimate_tiredness
        tired = estimate_tiredness()
        parts.append(f"[tiredness] {tired}%")

        return "\n".join(parts)


advisor = Advisor()
