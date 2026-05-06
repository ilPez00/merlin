"""
Merlin — Persistent goal store.
Goals live in ~/.merlin/goals.json and are loaded fresh each advisor cycle.
Never reset between sessions. Set once, referenced forever.
"""

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("merlin.goals")

GOALS_PATH = Path.home() / ".merlin" / "goals.json"

_SCHEMA = {
    "core": [],           # top-level life goals, e.g. ["financial independence", "status"]
    "social": [],         # e.g. ["be attractive", "lead groups", "be memorable"]
    "professional": [],   # e.g. ["close deals", "get promoted", "build authority"]
    "academic": [],       # e.g. ["top grades", "impress professors"]
    "romantic": [],       # e.g. ["attract X type", "build tension"]
    "current_focus": "",  # which domain to prioritize right now
    "notes": "",          # free-form context Merlin should always carry
}


def load() -> dict:
    """Load goals from disk. Returns defaults if file missing."""
    if not GOALS_PATH.exists():
        return dict(_SCHEMA)
    try:
        data = json.loads(GOALS_PATH.read_text())
        merged = dict(_SCHEMA)
        merged.update(data)
        return merged
    except Exception as e:
        log.warning("could not load goals: %s", e)
        return dict(_SCHEMA)


def save(goals: dict) -> None:
    GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOALS_PATH.write_text(json.dumps(goals, indent=2, ensure_ascii=False))


def to_prompt_str(goals: dict) -> str:
    """Format goals as a dense string for injection into the advisor prompt."""
    lines = []
    focus = goals.get("current_focus", "")
    if focus:
        lines.append(f"CURRENT FOCUS: {focus}")
    for domain in ("core", "social", "professional", "romantic", "academic"):
        items = goals.get(domain, [])
        if items:
            lines.append(f"{domain.upper()}: " + " | ".join(str(i) for i in items))
    notes = goals.get("notes", "").strip()
    if notes:
        lines.append(f"NOTES: {notes}")
    return "\n".join(lines) if lines else "No goals set. Run: python -m ai.goals"


def set_goal(domain: str, items: list[str]) -> str:
    goals = load()
    if domain not in _SCHEMA:
        return f"Unknown domain '{domain}'. Valid: {', '.join(_SCHEMA.keys())}"
    goals[domain] = items
    save(goals)
    return f"Set {domain} goals: {items}"


def set_focus(focus: str) -> str:
    goals = load()
    goals["current_focus"] = focus.strip()
    save(goals)
    return f"Current focus set to: {focus}"


def set_notes(notes: str) -> str:
    goals = load()
    goals["notes"] = notes.strip()
    save(goals)
    return f"Notes updated."


# ── Interactive CLI setup ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== MERLIN GOAL SETUP ===\n")
    print("Enter goals as comma-separated values. Leave blank to keep existing.\n")

    goals = load()

    def _prompt(label: str, key: str):
        existing = goals.get(key, [])
        hint = ", ".join(existing) if existing else "none"
        raw = input(f"{label} [{hint}]: ").strip()
        if raw:
            goals[key] = [x.strip() for x in raw.split(",") if x.strip()]

    _prompt("Core life goals      (core)", "core")
    _prompt("Social goals         (social)", "social")
    _prompt("Professional goals   (professional)", "professional")
    _prompt("Romantic goals       (romantic)", "romantic")
    _prompt("Academic goals       (academic)", "academic")

    focus_hint = goals.get("current_focus") or "none"
    focus_raw = input(f"\nCurrent focus domain [{focus_hint}]: ").strip()
    if focus_raw:
        goals["current_focus"] = focus_raw

    notes_hint = goals.get("notes") or "none"
    notes_raw = input(f"Extra context/notes [{notes_hint}]: ").strip()
    if notes_raw:
        goals["notes"] = notes_raw

    save(goals)
    print(f"\n✓ Goals saved to {GOALS_PATH}\n")
    print(to_prompt_str(goals))
