"""
Merlin — User self-model.
Stores skills, strengths, weaknesses, personality, communication style.
Goals = what you want. Profile = who you are.
Advisor uses both: play to strengths, route around weaknesses, apply skills.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("merlin.profile")

PROFILE_PATH = Path.home() / ".merlin" / "profile.json"

_SCHEMA = {
    "strengths":           [],   # e.g. ["charisma", "humor", "quick thinking"]
    "weaknesses":          [],   # e.g. ["impatience", "over-explains", "avoids conflict"]
    "skills": {
        "professional":    [],   # e.g. ["negotiation", "Python", "public speaking"]
        "social":          [],   # e.g. ["storytelling", "reading people", "humor"]
        "physical":        [],   # e.g. ["athletic", "strong presence"]
        "other":           [],
    },
    "personality":         "",   # e.g. "INTJ, dominant, direct, competitive"
    "communication_style": "",   # e.g. "concise, assertive, sometimes blunt"
    "appearance_notes":    "",   # e.g. "tall, well-dressed, commands attention"
    "triggers":            [],   # things that make performance drop: e.g. ["nervousness makes me stiff"]
    "notes":               "",   # anything else Merlin should always factor in
}


def load() -> dict:
    if not PROFILE_PATH.exists():
        return dict(_SCHEMA)
    try:
        data = json.loads(PROFILE_PATH.read_text())
        merged = dict(_SCHEMA)
        merged.update(data)
        if "skills" not in merged or not isinstance(merged["skills"], dict):
            merged["skills"] = dict(_SCHEMA["skills"])
        return merged
    except Exception as e:
        log.warning("could not load profile: %s", e)
        return dict(_SCHEMA)


def save(profile: dict) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False))


def to_prompt_str(profile: dict) -> str:
    """Dense string injected into the advisor prompt."""
    lines = []

    strengths = profile.get("strengths", [])
    if strengths:
        lines.append("STRENGTHS: " + " | ".join(strengths))

    weaknesses = profile.get("weaknesses", [])
    if weaknesses:
        lines.append("WEAKNESSES: " + " | ".join(weaknesses))

    skills = profile.get("skills", {})
    skill_parts = []
    for domain, items in skills.items():
        if items:
            skill_parts.append(f"{domain}=[{', '.join(items)}]")
    if skill_parts:
        lines.append("SKILLS: " + " | ".join(skill_parts))

    personality = profile.get("personality", "").strip()
    if personality:
        lines.append(f"PERSONALITY: {personality}")

    comm = profile.get("communication_style", "").strip()
    if comm:
        lines.append(f"STYLE: {comm}")

    appearance = profile.get("appearance_notes", "").strip()
    if appearance:
        lines.append(f"APPEARANCE: {appearance}")

    triggers = profile.get("triggers", [])
    if triggers:
        lines.append("WATCH OUT FOR: " + " | ".join(triggers))

    notes = profile.get("notes", "").strip()
    if notes:
        lines.append(f"NOTES: {notes}")

    return "\n".join(lines) if lines else "No profile set. Run: python -m ai.profile"


# ── Helpers for tool calls ────────────────────────────────────────────────────

def set_field(field: str, value) -> str:
    profile = load()
    if field not in _SCHEMA:
        return f"Unknown field '{field}'. Valid: {', '.join(_SCHEMA.keys())}"
    profile[field] = value
    save(profile)
    return f"Profile updated: {field} = {json.dumps(value, ensure_ascii=False)}"


def set_skill(domain: str, items: list[str]) -> str:
    profile = load()
    if "skills" not in profile or not isinstance(profile["skills"], dict):
        profile["skills"] = dict(_SCHEMA["skills"])
    profile["skills"][domain] = items
    save(profile)
    return f"Skills[{domain}] = {items}"


# ── Interactive CLI setup ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== MERLIN PROFILE SETUP ===")
    print("Tell Merlin who you are. Comma-separated. Leave blank to keep existing.\n")

    profile = load()

    def _list_prompt(label: str, key: str):
        existing = profile.get(key, [])
        hint = ", ".join(existing) if existing else "none"
        raw = input(f"{label} [{hint}]: ").strip()
        if raw:
            profile[key] = [x.strip() for x in raw.split(",") if x.strip()]

    def _str_prompt(label: str, key: str):
        existing = profile.get(key, "") or "none"
        raw = input(f"{label} [{existing}]: ").strip()
        if raw:
            profile[key] = raw

    _list_prompt("Strengths                (strengths)", "strengths")
    _list_prompt("Weaknesses               (weaknesses)", "weaknesses")
    _list_prompt("Triggers / watch-outs    (triggers)", "triggers")

    print("\n── Skills ──")
    skills = profile.get("skills", dict(_SCHEMA["skills"]))
    for domain in ("professional", "social", "physical", "other"):
        existing = skills.get(domain, [])
        hint = ", ".join(existing) if existing else "none"
        raw = input(f"  {domain:16} [{hint}]: ").strip()
        if raw:
            skills[domain] = [x.strip() for x in raw.split(",") if x.strip()]
    profile["skills"] = skills

    print("\n── Character ──")
    _str_prompt("Personality              (personality)", "personality")
    _str_prompt("Communication style      (communication_style)", "communication_style")
    _str_prompt("Appearance notes         (appearance_notes)", "appearance_notes")
    _str_prompt("Extra notes              (notes)", "notes")

    save(profile)
    print(f"\n✓ Profile saved to {PROFILE_PATH}\n")
    print(to_prompt_str(profile))
