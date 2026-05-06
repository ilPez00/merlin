"""Dossier system — LLM-maintained profiles for people, places, events, activities.

Each entity type has a structured JSON dossier, built and refined by the LLM
every time new conversation data arrives. User can export/download dossiers."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("merlin.dossiers")

DATA_DIR = Path.home() / ".merlin" / "data"
DOSSIERS_PATH = DATA_DIR / "dossiers.json"
CONV_PATH = Path.home() / ".merlin" / "conversations.md"

EMPTY_DOSSIERS = {
    "people": {},
    "places": {},
    "events": {},
    "activities": {},
    "last_updated": 0,
    "conversation_lines_processed": 0,
}


class DossierStore:
    """Persistent dossier store with LLM update and local cue matching."""

    def __init__(self):
        self.data = dict(EMPTY_DOSSIERS)
        self.load()

    # ── Persistence ─────────────────────────────

    def load(self):
        if DOSSIERS_PATH.exists():
            try:
                self.data = json.loads(DOSSIERS_PATH.read_text())
                for k in EMPTY_DOSSIERS:
                    self.data.setdefault(k, EMPTY_DOSSIERS[k])
            except (json.JSONDecodeError, OSError):
                self.data = dict(EMPTY_DOSSIERS)

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.data["last_updated"] = time.time()
        DOSSIERS_PATH.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    # ── Export ──────────────────────────────────

    def export_markdown(self) -> str:
        """Return all dossiers as a readable Markdown string."""
        lines = ["# Merlin Dossiers", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]

        if self.data["people"]:
            lines.append("## 👤 People\n")
            for name, info in sorted(self.data["people"].items()):
                lines.append(f"### {name}")
                if info.get("relationship"):
                    lines.append(f"- **Relationship:** {info['relationship']}")
                if info.get("contexts"):
                    lines.append(f"- **Context:** {'; '.join(info['contexts'][:3])}")
                if info.get("interests"):
                    lines.append(f"- **Interests:** {', '.join(info['interests'][:3])}")
                if info.get("open_questions"):
                    lines.append(f"- **Open questions:** {'; '.join(info['open_questions'][:2])}")
                if info.get("promises"):
                    for p in info["promises"][:2]:
                        what = p.get("what", "")
                        to_who = p.get("to", "")
                        lines.append(f"- **Promise:** {what} ({'to ' + to_who if to_who else 'mentioned'})")
                if info.get("mentioned_count"):
                    lines.append(f"- **Mentioned:** {info['mentioned_count']} times")
                last = info.get("last_talk", "")
                if last:
                    lines.append(f"- **Last talked:** {last}")
                lines.append("")

        if self.data["places"]:
            lines.append("## 📍 Places\n")
            for name, info in sorted(self.data["places"].items()):
                tags = info.get("tags", [])
                tag_str = f" ({', '.join(tags)})" if tags else ""
                ctx = info.get("context", "")
                lines.append(f"- **{name}**{tag_str}: {ctx}")
            lines.append("")

        if self.data["events"]:
            lines.append("## 📅 Events\n")
            for name, info in sorted(self.data["events"].items()):
                date = info.get("date", "")
                people = info.get("people_met", [])
                topics = info.get("topics", [])
                parts = []
                if date:
                    parts.append(f"Date: {date}")
                if people:
                    parts.append(f"Met: {', '.join(people[:3])}")
                if topics:
                    parts.append(f"Topics: {', '.join(topics[:3])}")
                meta = " — " + " | ".join(parts) if parts else ""
                lines.append(f"- **{name}**{meta}")
            lines.append("")

        if self.data["activities"]:
            lines.append("## ⚡ Activities\n")
            for name, info in sorted(self.data["activities"].items()):
                exp = info.get("user_experience", "")
                with_who = info.get("discussed_with", [])
                parts = []
                if exp:
                    parts.append(f"Experience: {exp}")
                if with_who:
                    parts.append(f"Discussed with: {', '.join(with_who[:2])}")
                meta = f" ({'; '.join(parts)})" if parts else ""
                lines.append(f"- **{name}**{meta}")
            lines.append("")

        return "\n".join(lines)

    # ── LLM update ──────────────────────────────

    async def update_from_conversations(self):
        """Read new lines from conversations.md and ask LLM to update dossiers."""
        lines = self._get_new_lines()
        if not lines:
            return False

        existing_summary = self._summarize()
        prompt = (
            "You are Merlin's knowledge extraction system. Update the user's dossiers "
            "based on these NEW conversation lines and the EXISTING dossiers below.\n\n"
            "For each person, place, event, or activity mentioned in the new lines:\n"
            "- **People**: extract name, context/relationship, open questions (lines ending with ?), "
            "promises made (e.g. 'I'll send', 'I will'), interests, achievements, "
            "and whether they asked the user something (unanswered questions)\n"
            "- **Places**: locations discussed, context, tags like 'vacation', 'work', 'food'\n"
            "- **Events**: what, when, who was there, topics discussed\n"
            "- **Activities**: things the user or others do/experience, user's experience level\n\n"
            "Return ONLY a JSON object with updated dossiers. Structure:\n"
            '{"people": {"Name": {"contexts": [...], "relationship": "...", '
            '"open_questions": [...], "promises": [{"from": "me", "to": "...", "what": "..."}], '
            '"interests": [...], "last_talk": "YYYY-MM-DD", "mentioned_count": N}}, '
            '"places": {...}, "events": {...}, "activities": {...}}\n'
            "Merge with existing data — don't overwrite unless new info is contradictory.\n"
            "If nothing new to add, return: {\"updated\": false}"
        )

        from ai.session import MerlinSession
        session = MerlinSession()
        await session.start()

        try:
            response = await session._backend.complete(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": (
                        f"EXISTING dossiers summary:\n{existing_summary[:1500]}\n\n"
                        f"NEW conversation lines:\n{lines[:3000]}"
                    )},
                ],
                tools=None,
                system=prompt,
                max_tokens=2000,
                temperature=0.2,
            )
            result = (response.text or "").strip()
            if result and "{" in result:
                json_str = result[result.index("{"):result.rindex("}") + 1]
                updates = json.loads(json_str)
                if updates.get("updated") is False:
                    self.data["conversation_lines_processed"] += len(lines.split("\n"))
                    self.save()
                    return False
                self._merge(updates)
                self.data["conversation_lines_processed"] += len(lines.split("\n"))
                self.save()
                log.info("dossiers updated: %d people, %d places, %d events, %d activities",
                         len(self.data["people"]), len(self.data["places"]),
                         len(self.data["events"]), len(self.data["activities"]))
                return True
        except Exception as e:
            log.warning("dossier update error: %s", e)
        return False

    def _get_new_lines(self) -> str:
        """Return conversation lines not yet processed."""
        if not CONV_PATH.exists():
            return ""
        try:
            text = CONV_PATH.read_text(encoding="utf-8")
        except OSError:
            return ""
        lines = text.strip().split("\n")
        processed = self.data.get("conversation_lines_processed", 0)
        new_lines = lines[processed:]
        if not new_lines:
            return ""
        return "\n".join(new_lines)

    def _summarize(self) -> str:
        """Short summary of existing dossiers for the LLM prompt."""
        parts = []
        for cat in ["people", "places", "events", "activities"]:
            entries = self.data.get(cat, {})
            if entries:
                names = list(entries.keys())[:10]
                parts.append(f"{cat}: {', '.join(names)}")
        return "\n".join(parts) if parts else "(no existing dossiers)"

    def _merge(self, updates: dict):
        """Merge LLM updates into existing dossiers."""
        for cat in ["people", "places", "events", "activities"]:
            incoming = updates.get(cat, {})
            existing = self.data.setdefault(cat, {})
            for key, info in incoming.items():
                if key not in existing:
                    existing[key] = {}
                # Merge fields
                for field, value in info.items():
                    if isinstance(value, list):
                        existing[key].setdefault(field, [])
                        for item in value:
                            if item not in existing[key][field]:
                                existing[key][field].append(item)
                        # Trim
                        existing[key][field] = existing[key][field][:10]
                    elif isinstance(value, dict):
                        existing[key].setdefault(field, {})
                        existing[key][field].update(value)
                    else:
                        existing[key][field] = value
                # Increment mention count if new info
                existing[key]["mentioned_count"] = existing[key].get("mentioned_count", 0) + 1

    # ── Cue matching (local, no LLM) ────────────

    def match_cues(self, transcript: str) -> list[dict]:
        """Check transcript against dossiers. Returns list of cue dicts."""
        cues = []
        if not transcript or len(transcript) < 3:
            return cues

        t_lower = transcript.lower()

        # People
        for name, info in self.data.get("people", {}).items():
            first = name.split()[0].lower()
            if first in t_lower and len(first) > 2:
                ctx = info.get("contexts", [])
                ctx_str = f" — {ctx[0]}" if ctx else ""
                # Check unanswered questions
                qs = info.get("open_questions", [])
                if qs:
                    cues.append({
                        "type": "follow_up",
                        "text": f"{name} asked about: \"{qs[0][:60]}\" — bring it up.",
                        "priority": 9,
                    })
                else:
                    cues.append({
                        "type": "name_recall",
                        "text": f"That's {name}{ctx_str}",
                        "priority": 7,
                    })
                # Check promises to this person
                for p in info.get("promises", [])[:1]:
                    if p.get("from") == "me":
                        cues.append({
                            "type": "follow_up",
                            "text": f"You promised {p.get('to', '')}: {p.get('what', '')[:60]}",
                            "priority": 8,
                        })
                break

        # Activities (topic bridge)
        for activity, info in self.data.get("activities", {}).items():
            if activity.lower() in t_lower and len(activity) > 3:
                exp = info.get("user_experience", "")
                if exp:
                    cues.append({
                        "type": "topic_bridge",
                        "text": f"You know about this — {exp[:80]}",
                        "priority": 6,
                    })
                break

        # Check for achievements in transcript (local pattern)
        ach_pats = ["finished", "completed", "won", "earned", "built", "launched", "marathon", "promotion"]
        for pat in ach_pats:
            if pat in t_lower:
                cues.append({
                    "type": "compliment",
                    "text": "They mentioned an achievement — say congrats.",
                    "priority": 5,
                })
                break

        # Deduplicate
        seen = set()
        unique = []
        for c in sorted(cues, key=lambda x: -x["priority"]):
            if c["text"] not in seen:
                seen.add(c["text"])
                unique.append(c)
        return unique[:2]


dossiers = DossierStore()
