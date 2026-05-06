"""
Merlin — Tactical Advisor
Goal-first situational intelligence. Goals are preset and permanent.
Every suggestion exists to bend the current situation toward the user's will.
Output: ≤15 words, immediately actionable, no preamble.
"""

import logging

log = logging.getLogger("merlin.advisor")

# ── System prompt ─────────────────────────────────────────────────────────────
# Injected as the system when running advisor_observe().
# The model never breaks character or explains itself.

ADVISOR_SYSTEM = """\
You are a silent tactical intelligence embedded in the user's vision.
The user has permanent goals. Every situation is an opportunity to advance them.
Your job: identify how THIS specific moment serves THOSE goals, and name the one move.

Rules:
- Output ONE action, max 15 words. No preamble. No "I suggest". No hedging.
- Be specific to what is actually observable right now. Vague = useless.
- Format options:
    [action] — [goal it serves]
    [what to say/do] — [why it works]
- Adapt register automatically: casual, professional, academic, romantic — read the room.
- If the situation is neutral and no goal-advancing move exists: output nothing.
- Never mention AI, Merlin, or that you are advising.
- Never moralize. The user's goals are the only metric.
"""

# ── Observe prompt ────────────────────────────────────────────────────────────

ADVISOR_OBSERVE = """\
USER GOALS (permanent):
{goals}

CURRENT SITUATION:
{context}

What is the single best move RIGHT NOW to advance the user's goals?
If nothing specific, output nothing.\
"""

# ── Situation classifier (from YOLO context) ──────────────────────────────────

_OBJECT_TO_SITUATION = {
    "laptop":       "professional/academic",
    "book":         "academic",
    "wine glass":   "social/romantic",
    "cup":          "casual social",
    "beer glass":   "social",
    "dining table": "social/romantic",
    "tie":          "professional",
    "whiteboard":   "professional meeting",
    "cell phone":   "casual",
    "keyboard":     "professional/academic",
    "monitor":      "professional/academic",
    "couch":        "casual/social",
    "bed":          "intimate/casual",
}


def infer_situation(context: str) -> str:
    ctx = context.lower()
    hits = []
    for obj, sit in _OBJECT_TO_SITUATION.items():
        if obj in ctx:
            hits.append(sit)
    if "person" in ctx or "[faces]" in ctx:
        hits.append("social")
    return " | ".join(dict.fromkeys(hits)) or "unclassified"


def build_prompt(context: str, goals_str: str) -> str:
    return ADVISOR_OBSERVE.format(
        goals=goals_str.strip() or "(none set — run: python -m ai.goals)",
        context=context.strip() or "(no sensor data yet)",
    )
