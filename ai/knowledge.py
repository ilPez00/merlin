"""
Merlin — Personal knowledge graph.
Stores structured records about people, places, and events observed over time.
Auto-populated from face recognition, GPS, audio, and LLM extraction.
Used by advisor + session to inject rich personal context.

Storage layout:
  ~/.merlin/knowledge/
    people/<name>.json     — one file per known person
    places.json            — GPS-keyed location records
    events.json            — chronological event log
"""

import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("merlin.knowledge")

BASE = Path.home() / ".merlin" / "knowledge"
PEOPLE_DIR = BASE / "people"
PLACES_PATH = BASE / "places.json"
EVENTS_PATH = BASE / "events.json"

PLACE_RADIUS_M = 80   # GPS snap radius for place matching
MAX_NOTES = 30        # max notes per person before oldest are dropped
MAX_INTERACTIONS = 50


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ensure():
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    BASE.mkdir(parents=True, exist_ok=True)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    d1, d2 = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d1/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d2/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── People ────────────────────────────────────────────────────────────────────

def _person_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name.strip())
    return PEOPLE_DIR / f"{safe}.json"


def _person_defaults(name: str) -> dict:
    return {
        "name": name,
        "relationship": "",          # friend, client, romantic, colleague, family…
        "first_seen": _now(),
        "last_seen": _now(),
        "seen_count": 0,
        "places_seen": [],           # list of place names
        "notes": [],                 # ["likes golf", "hates mornings"]
        "interactions": [],          # [{date, summary, sentiment}]
        "tags": [],                  # quick labels
        "face_enrolled": False,
    }


def load_person(name: str) -> Optional[dict]:
    p = _person_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def save_person(record: dict) -> None:
    _ensure()
    _person_path(record["name"]).write_text(
        json.dumps(record, indent=2, ensure_ascii=False)
    )


def get_or_create_person(name: str) -> dict:
    rec = load_person(name)
    if rec is None:
        rec = _person_defaults(name)
        save_person(rec)
        log.info("new person: %s", name)
    return rec


def log_person_seen(name: str, place_name: str = "", context_note: str = "") -> dict:
    """Called automatically when a face is recognized. Updates seen stats."""
    rec = get_or_create_person(name)
    rec["last_seen"] = _now()
    rec["seen_count"] = rec.get("seen_count", 0) + 1
    if place_name and place_name not in rec.get("places_seen", []):
        rec.setdefault("places_seen", []).append(place_name)
    if context_note:
        note = f"[{_today()}] {context_note}"
        notes = rec.setdefault("notes", [])
        if note not in notes:
            notes.append(note)
            if len(notes) > MAX_NOTES:
                rec["notes"] = notes[-MAX_NOTES:]
    save_person(rec)
    return rec


def add_person_note(name: str, note: str) -> str:
    rec = get_or_create_person(name)
    entry = f"[{_today()}] {note}"
    notes = rec.setdefault("notes", [])
    notes.append(entry)
    if len(notes) > MAX_NOTES:
        rec["notes"] = notes[-MAX_NOTES:]
    save_person(rec)
    return f"Note added for {name}."


def add_interaction(name: str, summary: str, sentiment: str = "neutral") -> str:
    rec = get_or_create_person(name)
    interactions = rec.setdefault("interactions", [])
    interactions.append({"date": _today(), "summary": summary, "sentiment": sentiment})
    if len(interactions) > MAX_INTERACTIONS:
        rec["interactions"] = interactions[-MAX_INTERACTIONS:]
    save_person(rec)
    return f"Interaction logged for {name}."


def set_relationship(name: str, relationship: str) -> str:
    rec = get_or_create_person(name)
    rec["relationship"] = relationship
    save_person(rec)
    return f"{name} → relationship: {relationship}"


def who_is(name: str) -> str:
    rec = load_person(name)
    if not rec:
        return f"No record found for '{name}'."
    lines = [f"Name: {rec['name']}"]
    if rec.get("relationship"):
        lines.append(f"Relationship: {rec['relationship']}")
    lines.append(f"Seen {rec.get('seen_count', 0)} times — last: {rec.get('last_seen', '?')[:10]}")
    if rec.get("places_seen"):
        lines.append(f"Places: {', '.join(rec['places_seen'][-5:])}")
    if rec.get("notes"):
        lines.append("Notes:\n  " + "\n  ".join(rec["notes"][-8:]))
    if rec.get("interactions"):
        last = rec["interactions"][-3:]
        lines.append("Recent interactions:\n  " + "\n  ".join(
            f"{i['date']}: {i['summary']}" for i in last
        ))
    if rec.get("tags"):
        lines.append(f"Tags: {', '.join(rec['tags'])}")
    return "\n".join(lines)


def list_people() -> list[str]:
    _ensure()
    return sorted(p.stem for p in PEOPLE_DIR.glob("*.json"))


def people_context_str(names: list[str]) -> str:
    """Compact multi-person summary for injection into advisor prompt."""
    parts = []
    for name in names:
        rec = load_person(name)
        if not rec:
            continue
        rel = rec.get("relationship", "")
        last_notes = rec.get("notes", [])[-3:]
        last_interaction = rec.get("interactions", [{}])[-1].get("summary", "")
        desc = f"{name}"
        if rel:
            desc += f" ({rel})"
        if last_interaction:
            desc += f" — last: {last_interaction[:80]}"
        if last_notes:
            desc += " | knows: " + "; ".join(n.split("] ")[-1] for n in last_notes[-2:])
        parts.append(desc)
    return "\n".join(parts)


# ── Places ────────────────────────────────────────────────────────────────────

def _load_places() -> list[dict]:
    if not PLACES_PATH.exists():
        return []
    try:
        return json.loads(PLACES_PATH.read_text())
    except Exception:
        return []


def _save_places(places: list[dict]) -> None:
    _ensure()
    PLACES_PATH.write_text(json.dumps(places, indent=2, ensure_ascii=False))


def find_place(lat: float, lon: float) -> Optional[dict]:
    for p in _load_places():
        if _haversine(lat, lon, p["lat"], p["lon"]) <= PLACE_RADIUS_M:
            return p
    return None


def log_place_visit(lat: float, lon: float, name: str = "", note: str = "") -> dict:
    places = _load_places()
    place = next(
        (p for p in places if _haversine(lat, lon, p["lat"], p["lon"]) <= PLACE_RADIUS_M),
        None,
    )
    if place is None:
        place = {
            "id": f"place_{int(time.time())}",
            "name": name or f"Location {lat:.4f},{lon:.4f}",
            "lat": lat, "lon": lon,
            "first_visit": _today(),
            "visit_count": 0,
            "last_visit": _today(),
            "people_seen_here": [],
            "notes": [],
        }
        places.append(place)
        log.info("new place: %s", place["name"])
    else:
        if name and not place.get("name", "").startswith("Location"):
            pass  # keep existing name
        elif name:
            place["name"] = name
    place["visit_count"] = place.get("visit_count", 0) + 1
    place["last_visit"] = _today()
    if note:
        place.setdefault("notes", []).append(f"[{_today()}] {note}")
    _save_places(places)
    return place


def add_person_to_place(lat: float, lon: float, person_name: str):
    places = _load_places()
    for p in places:
        if _haversine(lat, lon, p["lat"], p["lon"]) <= PLACE_RADIUS_M:
            seen = p.setdefault("people_seen_here", [])
            if person_name not in seen:
                seen.append(person_name)
    _save_places(places)


def place_context_str(lat: float, lon: float) -> str:
    place = find_place(lat, lon)
    if not place:
        return ""
    lines = [f"Location: {place['name']} (visited {place['visit_count']}x)"]
    if place.get("people_seen_here"):
        lines.append(f"People seen here before: {', '.join(place['people_seen_here'][-5:])}")
    if place.get("notes"):
        lines.append("Notes: " + " | ".join(n.split("] ")[-1] for n in place["notes"][-3:]))
    return "\n".join(lines)


# ── Events ────────────────────────────────────────────────────────────────────

def _load_events() -> list[dict]:
    if not EVENTS_PATH.exists():
        return []
    try:
        return json.loads(EVENTS_PATH.read_text())
    except Exception:
        return []


def log_event(summary: str, people: list[str] = None, place: str = "", tags: list[str] = None, outcome: str = "") -> str:
    events = _load_events()
    event = {
        "id": f"evt_{int(time.time())}",
        "timestamp": _now(),
        "date": _today(),
        "summary": summary,
        "people": people or [],
        "place": place,
        "outcome": outcome,
        "tags": tags or [],
    }
    events.append(event)
    # Keep last 500 events
    if len(events) > 500:
        events = events[-500:]
    _ensure()
    EVENTS_PATH.write_text(json.dumps(events, indent=2, ensure_ascii=False))
    log.info("event logged: %s", summary[:60])
    return f"Event logged: {summary[:80]}"


def recent_events(n: int = 10, person: str = "", place: str = "") -> list[dict]:
    events = _load_events()
    if person:
        events = [e for e in events if person in e.get("people", [])]
    if place:
        events = [e for e in events if place.lower() in e.get("place", "").lower()]
    return events[-n:]


def events_context_str(n: int = 5) -> str:
    evts = recent_events(n)
    if not evts:
        return ""
    lines = ["Recent events:"]
    for e in reversed(evts):
        who = ", ".join(e.get("people", [])) or "—"
        lines.append(f"  {e['date']}: {e['summary']} [with {who}]")
    return "\n".join(lines)
