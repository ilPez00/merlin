"""
Merlin — Tactical Advisor
Generates short, situation-specific suggestions toward the user's goals.
Output is always ≤20 words, immediately actionable, no preamble.
"""

import logging
from pathlib import Path

log = logging.getLogger("merlin.advisor")

# Injected into the LLM as system prompt when in ADVISOR mode
ADVISOR_SYSTEM = """\
You are a silent tactical advisor overlaid on the user's vision.
You observe their situation in real time: faces present, objects visible, audio heard, location.
You know their goals. You suggest ONE small, specific action they can take RIGHT NOW.

Rules:
- Max 15 words. No preamble. No explanation beyond the action itself.
- Be ruthlessly specific to what you actually observe. Generic = useless.
- Format: [action] — [one-word why]  e.g. "Lean in slightly — warmth"
- If nothing actionable is visible, return empty string. Do NOT invent observations.
- Adapt register to situation: casual/social, professional, academic, romantic.
- Never mention you are an AI or that you are advising.
"""

ADVISOR_OBSERVE_PROMPT = """\
Situation snapshot:
{context}

User goals: {goals}

Give your single best tactical suggestion right now. If nothing specific to act on, reply with nothing.\
"""

GOAL_KEYS = ["goals", "social_goals", "professional_goals", "academic_goals", "current_goal"]

SITUATION_HINTS = {
    # YOLO objects → situation type
    "laptop":      "professional/academic",
    "book":        "academic",
    "wine glass":  "social/romantic",
    "cup":         "casual social",
    "cell phone":  "casual",
    "tie":         "professional",
    "whiteboard":  "professional/academic meeting",
}


def classify_situation(context: str) -> str:
    """Heuristic: infer situation type from detected objects and faces."""
    ctx_lower = context.lower()
    hints = []
    for keyword, situation in SITUATION_HINTS.items():
        if keyword in ctx_lower:
            hints.append(situation)
    if "person" in ctx_lower or "face" in ctx_lower:
        hints.append("social")
    return ", ".join(dict.fromkeys(hints)) or "unknown"


def build_prompt(context: str, goals_str: str) -> str:
    return ADVISOR_OBSERVE_PROMPT.format(
        context=context.strip() or "(no sensor data yet)",
        goals=goals_str.strip() or "not specified — infer from context",
    )


def load_goals_str() -> str:
    """Read user goals from ~/.merlin/data/user_profile.json."""
    try:
        import json
        from pathlib import Path
        profile_path = Path.home() / ".merlin" / "data" / "user_profile.json"
        if not profile_path.exists():
            return ""
        profile = json.loads(profile_path.read_text())
        parts = []
        for key in GOAL_KEYS:
            val = profile.get(key)
            if val:
                if isinstance(val, dict):
                    parts.append(f"{key}: " + ", ".join(f"{k}={v}" for k, v in val.items()))
                elif isinstance(val, list):
                    parts.append(f"{key}: " + ", ".join(str(v) for v in val))
                else:
                    parts.append(f"{key}: {val}")
        return "\n".join(parts)
    except Exception as e:
        log.debug("could not load goals: %s", e)
        return ""
