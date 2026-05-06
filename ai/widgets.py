"""Widget registry — per-mode data sources and voice-addressable context strip items."""

import time
import logging
from pathlib import Path

log = logging.getLogger("merlin.widgets")

DATA_DIR = Path.home() / ".merlin" / "data"

# ── Widget definitions ────────────────────────────────────────────────────────

WIDGET_DEFS = {
    "loc": {
        "label": "📍",
        "desc": "GPS lat/lng + city",
        "source": "gps",
        "default_modes": ["WALK", "SCOUT", "DRIVE", "SKI"],
    },
    "alt": {
        "label": "↑",
        "desc": "Altitude meters",
        "source": "gps",
        "default_modes": ["DRIVE", "SKI", "SCOUT"],
    },
    "steps": {
        "label": "🚶",
        "desc": "Steps today",
        "source": "heuristic",
        "default_modes": ["WALK", "LIFT", "SCOUT"],
    },
    "wake_time": {
        "label": "☕",
        "desc": "When user woke up",
        "source": "config",
        "default_modes": ["WORK", "WALK", "NOTES"],
    },
    "money_spent": {
        "label": "💸",
        "desc": "Money spent today",
        "source": "tool",
        "default_modes": ["WORK", "WALK"],
    },
    "cal_burned": {
        "label": "🔥",
        "desc": "Calories burned today",
        "source": "tool",
        "default_modes": ["LIFT", "WALK", "SKI"],
    },
    "cal_consumed": {
        "label": "🍽️",
        "desc": "Calories consumed today",
        "source": "tool",
        "default_modes": [],
    },
    "tiredness": {
        "label": "😩",
        "desc": "Estimated tiredness %",
        "source": "heuristic",
        "default_modes": ["LIFT", "SCOUT", "SKI"],
    },
    "avg_time_spent": {
        "label": "📊",
        "desc": "Daily avg time per activity",
        "source": "heuristic",
        "default_modes": ["WORK"],
    },
    "todo": {
        "label": "📝",
        "desc": "Next 1-3 tasks",
        "source": "tool",
        "default_modes": ["WORK", "WALK", "DRIVE", "NOTES"],
    },
    "weather": {
        "label": "🌤️",
        "desc": "Weather at location",
        "source": "tool",
        "default_modes": ["SCOUT", "WALK", "DRIVE"],
    },
    "next_event": {
        "label": "📅",
        "desc": "Next calendar event",
        "source": "tool",
        "default_modes": ["WORK", "WALK"],
    },
}

# ── Default widget set per mode (max 4) ──────────────────────────────────────

MODE_WIDGETS = {
    "WORK":   ["wake_time", "todo", "avg_time_spent", "next_event"],
    "LIFT":   ["cal_burned", "tiredness", "steps"],
    "WALK":   ["loc", "steps", "cal_burned", "todo"],
    "TALK":   [],
    "NOTES":  ["wake_time", "loc", "todo"],
    "SCOUT":  ["loc", "alt", "steps", "tiredness"],
    "RECON":  [],
    "DRIVE":  ["loc", "alt", "todo", "weather"],
    "SKI":    ["alt", "cal_burned", "tiredness", "steps"],
}

# ── Runtime data store (populated by tools) ───────────────────────────────────

_runtime: dict = {
    "steps": 0,
    "wake_time": None,
    "money_spent": 0.0,
    "cal_burned": 0,
    "cal_consumed": 0,
    "daily_active_minutes": 0,
    "sleep_hours": 7.0,
    "todos": [],
}


def set(key: str, value):
    _runtime[key] = value


def get(key: str):
    return _runtime.get(key)


# ── Tiredness heuristic ──────────────────────────────────────────────────────

def estimate_tiredness() -> int:
    now = time.localtime()
    hour = now.tm_hour

    wake = _runtime.get("wake_time")
    if wake:
        wake_hour = wake
    else:
        wake_hour = 7  # default 7am

    hours_since_wake = max(0, hour - wake_hour + (24 if hour < wake_hour else 0))
    steps_today = _runtime.get("steps") or 0
    active_min = _runtime.get("daily_active_minutes") or 0
    sleep_hours = _runtime.get("sleep_hours") or 7.0

    wake_score = min(100, hours_since_wake * 5.0)
    step_score = min(100, steps_today / 15000 * 100)
    active_score = min(100, active_min / 480 * 100)
    sleep_debt = max(0, (8.0 - sleep_hours) * 12.5)
    circadian_dip = 25 if 13 <= hour <= 15 else 0

    tired = (
        wake_score * 0.30 +
        step_score * 0.20 +
        active_score * 0.15 +
        sleep_debt * 0.25 +
        circadian_dip * 0.10
    )
    return round(min(100, tired))


def tiredness_label(pct: int) -> str:
    if pct <= 20: return "🟢 Fresh"
    if pct <= 40: return "🟡 Mildly tired"
    if pct <= 60: return "🟠 Moderate"
    if pct <= 80: return "🔴 Fatigued"
    return "⚫ Exhausted"


# ── Widget value resolver ─────────────────────────────────────────────────────

def resolve(widget_id: str) -> str:
    """Return the display string for a widget ID, or empty string if unavailable."""
    defs = WIDGET_DEFS.get(widget_id)
    if not defs:
        return ""

    try:
        if widget_id == "loc":
            from ai.tools import _latest_gps
            g = _latest_gps
            if g and g.get("lat"):
                return f"📍 {g['lat']:.2f}, {g['lon']:.2f}"
            return "📍 --"
        if widget_id == "alt":
            from ai.tools import _latest_gps
            g = _latest_gps
            if g and g.get("alt"):
                return f"↑ {g['alt']:.0f}m"
            return "↑ --"
        if widget_id == "steps":
            s = _runtime.get("steps") or 0
            return f"🚶 {s/1000:.1f}k steps"
        if widget_id == "wake_time":
            w = _runtime.get("wake_time")
            if w is not None:
                return f"☕ Woke {int(w):02d}:00"
            return "☕ --"
        if widget_id == "money_spent":
            m = _runtime.get("money_spent") or 0
            return f"💸 €{m:.2f}"
        if widget_id == "cal_burned":
            c = _runtime.get("cal_burned") or 0
            return f"🔥 {c} kcal"
        if widget_id == "cal_consumed":
            c = _runtime.get("cal_consumed") or 0
            return f"🍽️ {c} kcal"
        if widget_id == "tiredness":
            pct = estimate_tiredness()
            return f"😩 {pct}% {tiredness_label(pct).split()[1]}"
        if widget_id == "avg_time_spent":
            # Simplified: just shows current mode minutes
            return f"📊 --"
        if widget_id == "todo":
            todos = _runtime.get("todos") or []
            remaining = len([t for t in todos if not t.get("done")])
            return f"📝 {remaining} todo{'s' if remaining != 1 else ''}"
        if widget_id == "weather":
            return f"🌤️ --"
        if widget_id == "next_event":
            return f"📅 --"
    except Exception as e:
        log.debug("widget %s error: %s", widget_id, e)

    return ""
