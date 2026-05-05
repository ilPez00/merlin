"""
Merlin — Agent tools
Tools the AI agent can call to interact with the PC filesystem, shell,
phone filesystem, and the user's lifestyle data (exercises, food, places, goals).
"""

import asyncio
import json
import logging
import os
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("merlin.tools")

# ── Phone-file relay state ────────────────────────────────────────────────────
# Populated by server when file_content arrives from phone.

_pending_phone_files: dict[str, asyncio.Future] = {}
_send_to_phone: Any = None  # coroutine callable set by server at startup
_latest_gps: dict | None = None  # latest GPS from phone, set via set_latest_gps


def set_phone_sender(fn):
    """Register the async send-to-phone callable (set by server.py)."""
    global _send_to_phone
    _send_to_phone = fn


def set_latest_gps(gps: dict | None):
    """Set latest GPS coordinates (called by stream_processor)."""
    global _latest_gps
    _latest_gps = gps


def resolve_phone_file(path: str, content: str):
    """Called by the WebSocket handler when the phone sends file_content."""
    fut = _pending_phone_files.pop(path, None)
    if fut and not fut.done():
        fut.set_result(content)


# ── Helpers ────────────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".merlin" / "data"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(name: str) -> list | dict:
    _ensure_data_dir()
    path = DATA_DIR / name
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return [] if name.endswith("s.json") else {}
    return [] if name.endswith("s.json") else {}


def _write_json(name: str, data: list | dict):
    _ensure_data_dir()
    (DATA_DIR / name).write_text(json.dumps(data, indent=2, default=str))


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── Safety check for shell commands ──────────────────────────────────────────

_BLOCKED: list[tuple[str, str]] = [
    ("rm -rf /",   "would delete root filesystem"),
    ("rm -rf /*",  "would delete root filesystem"),
    (":(){:|:&};:", "fork bomb"),
    ("mkfs.",      "would format a disk"),
]


def _safety_check(cmd: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Blocks only the most catastrophic commands."""
    for pattern, reason in _BLOCKED:
        if pattern in cmd:
            return False, reason
    return True, ""


# ── Tool implementations ──────────────────────────────────────────────────────

async def read_file(path: str) -> str:
    """Read a file from the PC filesystem."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Error: file not found: {path}"
        if not p.is_file():
            return f"Error: not a file: {path}"
        content = p.read_bytes()[:65536]
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return f"[binary file, {len(content)} bytes, not displayable as text]"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


async def write_file(path: str, content: str) -> str:
    """Write content to a file on the PC filesystem."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


async def list_dir(path: str = ".") -> str:
    """List the contents of a directory on the PC."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Error: directory not found: {path}"
        if not p.is_dir():
            return f"Error: not a directory: {path}"
        entries = []
        for entry in sorted(p.iterdir()):
            kind = "DIR" if entry.is_dir() else "FILE"
            try:
                size = entry.stat().st_size if entry.is_file() else 0
                entries.append(f"{kind:4}  {entry.name}  ({size} bytes)" if kind == "FILE"
                                else f"{kind:4}  {entry.name}/")
            except OSError:
                entries.append(f"???   {entry.name}")
        return "\n".join(entries) if entries else "(empty directory)"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error listing {path}: {e}"


async def run_shell(cmd: str) -> str:
    """Run a shell command on the PC and return stdout + stderr."""
    safe, reason = _safety_check(cmd)
    if not safe:
        return f"Error: command blocked ({reason}): {cmd}"

    log.info("shell: %s", cmd)
    try:
        result = await asyncio.create_subprocess_shell(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30.0)
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        parts = []
        if out.strip():
            parts.append(out.strip())
        if err.strip():
            parts.append(f"[stderr]\n{err.strip()}")
        return "\n".join(parts) if parts else f"(exit {result.returncode}, no output)"
    except asyncio.TimeoutError:
        return "Error: command timed out after 30 seconds"
    except Exception as e:
        return f"Error running command: {e}"


async def read_phone_file(path: str) -> str:
    """Request a file from the phone over WebSocket and return its content."""
    if _send_to_phone is None:
        return "Error: no phone connection available"

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending_phone_files[path] = fut

    await _send_to_phone({"type": "request_file", "path": path})
    log.info("waiting for phone file: %s", path)

    try:
        content = await asyncio.wait_for(asyncio.shield(fut), timeout=30.0)
        return content
    except asyncio.TimeoutError:
        _pending_phone_files.pop(path, None)
        return f"Error: phone did not respond with {path} within 30 seconds"


# ── Lifestyle tools ────────────────────────────────────────────────────────────

async def log_exercise(exercise: str, reps: int, sets: int = 1) -> str:
    """Log an exercise session to the user's daily log."""
    total = reps * sets
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": _today(),
        "exercise": exercise.lower().strip(),
        "reps": reps,
        "sets": sets,
        "total_reps": total,
    }
    data = _read_json("exercise_log.json")
    if not isinstance(data, list):
        data = []
    data.append(entry)
    _write_json("exercise_log.json", data)

    today_total = sum(
        e["total_reps"]
        for e in data
        if isinstance(e, dict) and e.get("date") == _today()
    )
    return (
        f"Logged {sets} set(s) of {reps} {exercise} reps "
        f"(total today: {today_total})"
    )


async def log_food(
    food: str,
    calories: int,
    protein: int = 0,
    carbs: int = 0,
    fat: int = 0,
) -> str:
    """Log a food item with estimated macros."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": _today(),
        "food": food.strip(),
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
    }
    data = _read_json("food_log.json")
    if not isinstance(data, list):
        data = []
    data.append(entry)
    _write_json("food_log.json", data)

    today_cals = sum(
        e.get("calories", 0)
        for e in data
        if isinstance(e, dict) and e.get("date") == _today()
    )
    return (
        f"Logged {food}: {calories} kcal "
        f"(P:{protein}g C:{carbs}g F:{fat}g). "
        f"Total today: {today_cals} kcal"
    )


async def get_user_pref(key: str) -> str:
    """Read a user preference or goal. Returns the value or 'not set'."""
    profile = _read_json("user_profile.json")
    if not isinstance(profile, dict):
        return "Error: user profile not initialized"
    val = profile.get(key)
    if val is None:
        return f"Preference '{key}' is not set"
    if isinstance(val, dict) or isinstance(val, list):
        return json.dumps(val, indent=2)
    return str(val)


async def set_user_pref(key: str, value: Any) -> str:
    """Set a user preference or goal. Creates the profile if needed."""
    profile = _read_json("user_profile.json")
    if not isinstance(profile, dict):
        profile = {}
    profile[key] = value
    _write_json("user_profile.json", profile)
    return f"Set {key} = {json.dumps(value)}"


async def find_places(query: str) -> str:
    """Find nearby places using OpenStreetMap Nominatim."""
    if not _latest_gps:
        return (
            "Error: no GPS data available. "
            "Make sure the phone is connected and GPS is enabled."
        )
    lat = _latest_gps.get("lat", 0)
    lon = _latest_gps.get("lon", 0)

    import requests as req

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "dedup": 1,
    }
    headers = {"User-Agent": "MerlinLifestyleAI/1.0"}
    try:
        resp = req.get(url, params=params, headers=headers, timeout=10)
        results = resp.json()
        if not results:
            return f"No places found matching '{query}' near your location."
        lines = [f"Nearby {query}:"]
        for r in results:
            dist_m = ((float(r["lat"]) - lat) ** 2 + (float(r["lon"]) - lon) ** 2) ** 0.5 * 111000
            label = r.get("display_name", r.get("name", "unknown"))
            lines.append(f"  {label} ({dist_m:.0f}m away)")
        return "\n".join(lines)
    except Exception as e:
        return f"Error finding places: {e}"


async def bookmark_place(name: str, lat: float, lon: float) -> str:
    """Save a place to the user's bookmarks."""
    entry = {
        "name": name.strip(),
        "lat": lat,
        "lon": lon,
        "bookmarked_at": datetime.now().isoformat(),
    }
    data = _read_json("places.json")
    if not isinstance(data, list):
        data = []
    data.append(entry)
    _write_json("places.json", data)
    return f"Bookmarked {name}"


async def check_goals() -> str:
    """Check today's progress against configured daily goals."""
    profile = _read_json("user_profile.json")
    if not isinstance(profile, dict):
        return "No user profile found. Use set_user_pref to configure goals."

    goals = profile.get("goals", {})
    if not goals:
        return "No daily goals configured. Use set_user_pref goals=... to set them."

    exercises = _read_json("exercise_log.json")
    foods = _read_json("food_log.json")
    today = _today()

    today_exercise_reps = {}
    for e in exercises:
        if isinstance(e, dict) and e.get("date") == today:
            ex = e.get("exercise", "")
            today_exercise_reps[ex] = today_exercise_reps.get(ex, 0) + e.get("total_reps", 0)

    today_calories = sum(
        e.get("calories", 0) for e in foods if isinstance(e, dict) and e.get("date") == today
    )

    lines = ["Today's progress:"]
    all_met = True

    for goal_key, goal_val in goals.items():
        achieved = 0
        if goal_key in today_exercise_reps:
            achieved = today_exercise_reps[goal_key]
        elif goal_key == "calories":
            achieved = today_calories

        pct = min(100, int(achieved / goal_val * 100)) if goal_val > 0 else 0
        icon = "✓" if pct >= 100 else "→"
        if pct < 100:
            all_met = False
        lines.append(f"  {icon} {goal_key}: {achieved}/{goal_val} ({pct}%)")

    if all_met and lines:
        lines.append("All goals met! Great work today.")
    elif lines:
        lines.append("Keep going!")

    return "\n".join(lines)


# ── HUD/translation tools ─────────────────────────────────────────────────────

_latest_backend = None  # set by session/agent for LLM-based translation


def set_latest_backend(backend):
    global _latest_backend
    _latest_backend = backend


async def capture_screen() -> str:
    """Capture the PC desktop screen and return it as a base64 JPEG for AI analysis."""
    try:
        import mss
        import base64
        from PIL import Image
        import io

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=50)
            b64 = base64.b64encode(buf.getvalue()).decode()
            return f"data:image/jpeg;base64,{b64}"
    except ImportError:
        return "Error: mss/Pillow not installed. Run: pip install mss"
    except Exception as e:
        return f"Error capturing screen: {e}"


async def translate_text(text: str, target_lang: str = "en") -> str:
    """Translate text to the target language using the AI backend."""
    if not text.strip():
        return ""
    from server.translate import translate_text as _do_translate
    return await _do_translate(text, target_lang, backend=_latest_backend)


async def get_navigation(destination_lat: float, destination_lon: float) -> str:
    """Get turn-by-turn navigation directions from current GPS to destination."""
    if not _latest_gps:
        return "Error: no GPS data available. Make sure the phone is connected."

    src_lat = _latest_gps.get("lat", 0)
    src_lon = _latest_gps.get("lon", 0)

    import requests as req
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{src_lon},{src_lat};{destination_lon},{destination_lat}"
        f"?steps=true&geometries=geojson&overview=full"
    )
    try:
        resp = req.get(url, timeout=15)
        data = resp.json()
        if data["code"] != "Ok" or not data["routes"]:
            return f"Error: could not find route. {data.get('message', '')}"

        route = data["routes"][0]
        total_dist = route["distance"]
        total_time = route["duration"]
        legs = route["legs"][0] if route.get("legs") else None
        steps = legs["steps"] if legs else []

        lines = [
            f"Route: {total_dist:.0f}m ({total_time / 60:.0f} min)"
        ]
        for step in steps:
            instruction = step.get("maneuver", {}).get("type", "continue")
            name = step.get("name", "")
            dist = step.get("distance", 0)
            modifier = step.get("maneuver", {}).get("modifier", "")
            turn_str = f"{modifier} {instruction}" if modifier else instruction
            lines.append(f"  {turn_str} on {name} ({dist:.0f}m)" if name else f"  {turn_str} ({dist:.0f}m)")

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting navigation: {e}"


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "read_file":       read_file,
    "write_file":      write_file,
    "list_dir":        list_dir,
    "run_shell":       run_shell,
    "read_phone_file": read_phone_file,
    "log_exercise":    log_exercise,
    "log_food":        log_food,
    "get_user_pref":   get_user_pref,
    "set_user_pref":   set_user_pref,
    "find_places":     find_places,
    "bookmark_place":  bookmark_place,
    "check_goals":     check_goals,
    "capture_screen":  capture_screen,
    "translate_text":  translate_text,
    "get_navigation":  get_navigation,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the PC filesystem. Limited to 64 KB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to the file."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on the PC filesystem. Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Destination file path."},
                    "content": {"type": "string", "description": "Text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the contents of a directory on the PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current directory)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command on the PC. Returns stdout and stderr. Times out after 30 s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Shell command to execute."},
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_phone_file",
            "description": "Request the user's phone to send a specific file. The phone will prompt the user to select the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path/name of the file to request from the phone."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_exercise",
            "description": "Log an exercise session. Records reps, sets, and exercise type to the user's daily log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {"type": "string", "description": "Exercise name (e.g. pushups, squats, curls)."},
                    "reps":     {"type": "integer", "description": "Number of repetitions completed."},
                    "sets":     {"type": "integer", "description": "Number of sets completed (default: 1)."},
                },
                "required": ["exercise", "reps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_food",
            "description": "Log a food item with estimated macros. Records to the user's daily food log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food":     {"type": "string", "description": "Food name/description."},
                    "calories": {"type": "integer", "description": "Estimated calories."},
                    "protein":  {"type": "integer", "description": "Protein in grams (optional)."},
                    "carbs":    {"type": "integer", "description": "Carbohydrates in grams (optional)."},
                    "fat":      {"type": "integer", "description": "Fat in grams (optional)."},
                },
                "required": ["food", "calories"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_pref",
            "description": "Read a user preference or daily goal. Returns the value or 'not set'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key (e.g. 'name', 'goals', 'weight')."},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_user_pref",
            "description": "Set a user preference or daily goal. Creates the profile if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key":   {"type": "string", "description": "Preference key (e.g. 'goals', 'name', 'weight')."},
                    "value": {"description": "Value to set. Can be string, number, or object (e.g. goals: {pushups: 50})."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_places",
            "description": "Find nearby places matching a query using OpenStreetMap. Requires GPS from the phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for (e.g. 'coffee shop', 'gym', 'park')."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bookmark_place",
            "description": "Save a place to the user's bookmarks for later reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name/label for this place."},
                    "lat":  {"type": "number", "description": "Latitude."},
                    "lon":  {"type": "number", "description": "Longitude."},
                },
                "required": ["name", "lat", "lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_goals",
            "description": "Check today's progress against configured daily goals (e.g. pushups, calories). Shows percentages.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Capture the PC desktop screen as an image. Returns a base64 JPEG that the AI can analyze to see what you're working on.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translate text to a target language. Useful for real-time conversation translation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate."},
                    "target_lang": {"type": "string", "description": "Target language code (e.g. 'en', 'it', 'fr', 'es', 'de', 'ja', 'zh'). Default: 'en'."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_navigation",
            "description": "Get turn-by-turn driving directions from current GPS location to a destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination_lat": {"type": "number", "description": "Destination latitude."},
                    "destination_lon": {"type": "number", "description": "Destination longitude."},
                },
                "required": ["destination_lat", "destination_lon"],
            },
        },
    },
]


async def call_tool(name: str, arguments: dict) -> str:
    """Dispatch a tool call by name and return the result as a string."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        result = await fn(**arguments)
        return str(result)
    except TypeError as e:
        return f"Error: bad arguments for tool '{name}': {e}"
    except Exception as e:
        log.error("tool %s error: %s", name, e)
        return f"Error in tool '{name}': {e}"
