"""
Merlin — Agent tools
Tools the AI agent can call to interact with the PC filesystem, shell,
phone filesystem, and the user's lifestyle data (exercises, food, places, goals).
"""

import asyncio
import json
import logging
import math
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
_latest_frame: bytes | None = None  # latest camera frame, set by stream_processor


def set_phone_sender(fn):
    """Register the async send-to-phone callable (set by server.py)."""
    global _send_to_phone
    _send_to_phone = fn


def set_latest_gps(gps: dict | None):
    """Set latest GPS coordinates (called by stream_processor)."""
    global _latest_gps
    _latest_gps = gps


def set_latest_frame(frame: bytes | None):
    """Set latest camera JPEG frame (called by stream_processor)."""
    global _latest_frame
    _latest_frame = frame


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
            rlat, rlon = float(r["lat"]), float(r["lon"])
            dlat = math.radians(rlat - lat)
            dlon = math.radians(rlon - lon)
            a = (math.sin(dlat / 2) ** 2
                 + math.cos(math.radians(lat)) * math.cos(math.radians(rlat)) * math.sin(dlon / 2) ** 2)
            dist_m = 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
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


# ── Desktop-specific tools ────────────────────────────────────────────────────

_latest_webcam_b64: str | None = None
_latest_sudo_password: str | None = None


def set_webcam_frame(b64: str | None):
    global _latest_webcam_b64
    _latest_webcam_b64 = b64


def set_sudo_password(pw: str | None):
    global _latest_sudo_password
    _latest_sudo_password = pw


async def capture_webcam() -> str:
    """Capture the current webcam frame and return it as a base64 JPEG, or a status message."""
    if _latest_webcam_b64:
        return f"data:image/jpeg;base64,{_latest_webcam_b64}"
    return "No webcam frame available. The webcam may not be active."


async def speak(text: str) -> str:
    """Speak the given text aloud using text-to-speech. The user hears this through their speakers."""
    try:
        import edge_tts
        import subprocess
        from pathlib import Path

        voice = "en-US-JennyNeural"
        tts = edge_tts.Communicate(str(text)[:500], voice)
        await tts.save("/tmp/merlin_tts.mp3")
        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "/tmp/merlin_tts.mp3"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Spoken: {text[:100]}..."
    except ImportError:
        return "Error: edge-tts not installed"
    except Exception as e:
        return f"Error speaking: {e}"


# ── Modify run_shell to support sudo ──────────────────────────────────────────

_original_run_shell = run_shell


async def _sudo_run_shell(cmd: str) -> str:
    """Extended run_shell with sudo support via per-command password prompt."""
    if cmd.strip().startswith("sudo ") and _latest_sudo_password:
        import asyncio, subprocess
        full_cmd = f"sudo -S {cmd[5:]}"
        try:
            result = await asyncio.create_subprocess_shell(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                result.communicate(input=(_latest_sudo_password + "\n").encode()),
                timeout=60,
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            parts = []
            if out: parts.append(out)
            if err: parts.append(f"[stderr]\n{err}")
            return "\n".join(parts) if parts else f"(exit {result.returncode}, no output)"
        except asyncio.TimeoutError:
            return "Error: command timed out after 60 seconds"
        except Exception as e:
            return f"Error running command: {e}"
    elif cmd.strip().startswith("sudo "):
        return "Error: sudo password not provided. Prompt the user to speak or type their sudo password."
    return await _original_run_shell(cmd)


# ── Goal tools ────────────────────────────────────────────────────────────────

async def show_goals() -> str:
    """Show the user's current persistent goals."""
    from .goals import load, to_prompt_str
    return to_prompt_str(load())


async def update_goal(domain: str, items: list) -> str:
    """Update goals for a specific domain (core/social/professional/romantic/academic)."""
    from .goals import set_goal
    return set_goal(domain, [str(i) for i in items])


async def set_current_focus(focus: str) -> str:
    """Set the current priority focus domain (e.g. 'social', 'professional')."""
    from .goals import set_focus
    return set_focus(focus)


async def add_goal_note(note: str) -> str:
    """Add or replace the contextual notes Merlin carries about the user's situation."""
    from .goals import set_notes
    return set_notes(note)


# ── Profile tools ──────────────────────────────────────────────────────────────

async def show_profile() -> str:
    """Show the user's full skill/strength/weakness profile."""
    from .profile import load, to_prompt_str
    return to_prompt_str(load())


async def update_strengths(items: list) -> str:
    """Set the user's strengths list."""
    from .profile import set_field
    return set_field("strengths", [str(i) for i in items])


async def update_weaknesses(items: list) -> str:
    """Set the user's weaknesses list."""
    from .profile import set_field
    return set_field("weaknesses", [str(i) for i in items])


async def update_skills(domain: str, items: list) -> str:
    """Set skills for a domain: professional, social, physical, or other."""
    from .profile import set_skill
    return set_skill(domain, [str(i) for i in items])


async def update_profile_field(field: str, value: str) -> str:
    """Set a profile text field: personality, communication_style, appearance_notes, triggers, notes."""
    from .profile import set_field, load
    profile = load()
    if field in ("triggers",):
        return set_field(field, [v.strip() for v in value.split(",") if v.strip()])
    return set_field(field, value)


# ── Face recognition tools ────────────────────────────────────────────────────

async def enroll_face(name: str) -> str:
    """Enroll a person's face using the current camera frame."""
    if not _latest_frame:
        return "No camera frame available. Make sure the phone camera is streaming and the person is visible."
    try:
        from vision.face_recognizer import enroll_sync, invalidate_cache
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, enroll_sync, name, _latest_frame)
        invalidate_cache()
        return result
    except RuntimeError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error enrolling face: {e}"


async def forget_face(name: str) -> str:
    """Remove a person from the face recognition database."""
    try:
        from vision.face_recognizer import forget_sync, invalidate_cache
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, forget_sync, name)
        invalidate_cache()
        return result
    except Exception as e:
        return f"Error: {e}"


async def list_known_faces() -> str:
    """List all people enrolled in the face recognition database."""
    try:
        from vision.face_recognizer import list_enrolled
        names = list_enrolled()
        if not names:
            return "No faces enrolled. Use enroll_face(name) while the person is visible on camera."
        return "Known faces: " + ", ".join(names)
    except Exception as e:
        return f"Error: {e}"


# ── Memory search tool ────────────────────────────────────────────────────────

async def search_memory(query: str, n: int = 5) -> str:
    """Search episodic memory for relevant past observations and Q&A."""
    try:
        from .memory import get_memory
        results = get_memory().query(query, n=n)
        if not results:
            return "No relevant memories found."
        return "\n\n".join(results)
    except Exception as e:
        return f"Memory search error: {e}"


# ── Lifestyle tools: tiredness, expense, sleep, todos ──────────────────────────

async def log_sleep(hours: float, quality: str = "good") -> str:
    """Log sleep hours and quality rating."""
    from ai.widgets import set as wset
    wset("sleep_hours", hours)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": _today(),
        "hours": hours,
        "quality": quality,
    }
    data = _read_json("sleep_log.json")
    if not isinstance(data, list): data = []
    data.append(entry)
    _write_json("sleep_log.json", data)
    return f"Logged {hours}h of sleep (quality: {quality})"


async def log_expense(amount: float, category: str = "other", note: str = "") -> str:
    """Log a money expense. Updates today's total spent."""
    from ai.widgets import set as wset
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": _today(),
        "amount": amount,
        "category": category.strip().lower(),
        "note": note.strip(),
    }
    data = _read_json("expenses.json")
    if not isinstance(data, list): data = []
    data.append(entry)
    _write_json("expenses.json", data)

    # Update runtime total
    today_total = sum(
        e.get("amount", 0) for e in data
        if isinstance(e, dict) and e.get("date") == _today()
    )
    wset("money_spent", today_total)
    return f"Logged €{amount:.2f} ({category}). Today total: €{today_total:.2f}"


async def get_tiredness() -> str:
    """Estimate the user's current tiredness level based on wake time, steps, sleep, and activity."""
    from ai.widgets import estimate_tiredness, tiredness_label
    pct = estimate_tiredness()
    label = tiredness_label(pct)
    return f"Tiredness: {pct}% ({label})"


async def get_todo_list() -> str:
    """List the user's todo items."""
    data = _read_json("todos.json")
    if not isinstance(data, list) or not data:
        return "No todos."
    lines = []
    for i, t in enumerate(data, 1):
        status = "✓" if t.get("done") else "○"
        lines.append(f"{i}. {status} {t.get('text', '')}")
    return "\n".join(lines)


async def add_todo(text: str, priority: str = "medium") -> str:
    """Add a todo item."""
    from ai.widgets import set as wset
    data = _read_json("todos.json")
    if not isinstance(data, list): data = []
    entry = {
        "id": str(len(data) + 1),
        "text": text.strip(),
        "done": False,
        "priority": priority,
        "created": datetime.now().isoformat(),
    }
    data.append(entry)
    _write_json("todos.json", data)
    wset("todos", data)
    return f"Added: {text}"


async def complete_todo(item_id: str) -> str:
    """Mark a todo item as complete by ID or number."""
    from ai.widgets import set as wset
    data = _read_json("todos.json")
    if not isinstance(data, list): return "No todos found."
    for t in data:
        if t.get("id") == item_id or str(t.get("id")) == item_id:
            t["done"] = True
            t["completed_at"] = datetime.now().isoformat()
            _write_json("todos.json", data)
            wset("todos", data)
            return f"Completed: {t.get('text', '')}"
    return f"Todo '{item_id}' not found."


# ── Conversate-style tools (Prep Notes, AI Summary, AI Cues) ──────────────────

async def log_prep_note(text: str, topic: str = "") -> str:
    """Save a preparation note for an upcoming conversation. The AI will use this as context during the next TALK mode session."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic.strip() or "general",
        "text": text.strip(),
    }
    data = _read_json("prep_notes.json")
    if not isinstance(data, list): data = []
    data.append(entry)
    _write_json("prep_notes.json", data)
    return f"Prep note saved (topic: {topic or 'general'}). I'll reference this in your next conversation."


async def conversation_summary() -> str:
    """Generate a summary of the most recent conversation from the diary. Returns key points and action items."""
    recent = _read_json("conversations.json") if False else []
    # Fallback: return recent prep notes and diary entries
    prep = _read_json("prep_notes.json")[-3:] if _read_json("prep_notes.json") else []
    lines = ["No recent conversation data available."]
    if prep:
        lines.append("Recent prep notes:")
        for p in prep:
            lines.append(f"  - {p.get('text', '')[:100]}")
    return "\n".join(lines)


async def get_conversation_cue(context: str = "") -> str:
    """Get a real-time conversation cue — a suggestion, answer, concept explanation, or bio reference based on what's being discussed."""
    if context:
        return f"Conversation cue for '{context}' would appear here. The AI will use this context in the conversation."
    return "No context provided for a cue."


# ── Memory tools (ChromaDB stubs for future) ─────────────────────────────────

_memory_store: list[dict] = []


async def memory_search(query: str, n: int = 5) -> str:
    """Search stored memories by text query."""
    if not _memory_store:
        return "No memories stored yet."
    # Simple keyword fallback until ChromaDB is wired
    results = [m for m in _memory_store if query.lower() in m.get("text", "").lower()]
    if not results:
        return "No matching memories found."
    lines = []
    for m in results[:n]:
        lines.append(f"- {m.get('text', '')} ({m.get('timestamp', '')})")
    return "\n".join(lines)


async def memory_save(text: str, tags: str = "", importance: int = 1) -> str:
    """Save a memory for long-term recall."""
    entry = {
        "text": text.strip(),
        "tags": tags.strip().split(",") if tags else [],
        "importance": importance,
        "timestamp": datetime.now().isoformat(),
    }
    _memory_store.append(entry)
    # Also persist to disk
    data = _read_json("memories.json")
    if not isinstance(data, list): data = []
    data.append(entry)
    _write_json("memories.json", data)
    return f"Saved memory: {text[:60]}..."


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "read_file":           read_file,
    "write_file":          write_file,
    "list_dir":            list_dir,
    "run_shell":           _sudo_run_shell,
    "read_phone_file":     read_phone_file,
    "log_exercise":        log_exercise,
    "log_food":            log_food,
    "get_user_pref":       get_user_pref,
    "set_user_pref":       set_user_pref,
    "find_places":         find_places,
    "bookmark_place":      bookmark_place,
    "check_goals":         check_goals,
    "capture_screen":      capture_screen,
    "translate_text":      translate_text,
    "get_navigation":      get_navigation,
    "memory_search":       memory_search,
    "memory_save":         memory_save,
    "capture_webcam":      capture_webcam,
    "speak":               speak,
    "log_sleep":           log_sleep,
    "log_expense":         log_expense,
    "get_tiredness":       get_tiredness,
    "get_todo_list":       get_todo_list,
    "add_todo":            add_todo,
    "complete_todo":       complete_todo,
    "log_prep_note":       log_prep_note,
    "conversation_summary": conversation_summary,
    "get_conversation_cue": get_conversation_cue,
    "enroll_face":          enroll_face,
    "forget_face":          forget_face,
    "list_known_faces":     list_known_faces,
    "search_memory":        search_memory,
    "show_goals":           show_goals,
    "update_goal":          update_goal,
    "set_current_focus":    set_current_focus,
    "add_goal_note":        add_goal_note,
    "show_profile":         show_profile,
    "update_strengths":     update_strengths,
    "update_weaknesses":    update_weaknesses,
    "update_skills":        update_skills,
    "update_profile_field": update_profile_field,
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
            "name": "memory_search",
            "description": "Search stored memories by text query. Returns matching memories with similarity scores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory."},
                    "n":     {"type": "integer", "description": "Max results to return (default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_sleep",
            "description": "Log sleep hours and quality. Updates tiredness estimation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours":   {"type": "number", "description": "Hours slept."},
                    "quality": {"type": "string", "description": "Sleep quality: 'good', 'fair', 'poor'."},
                },
                "required": ["hours"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_expense",
            "description": "Log a money expense. Categorizes and tracks daily spending total.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount":   {"type": "number", "description": "Amount spent in EUR."},
                    "category": {"type": "string", "description": "Category: 'food', 'transport', 'shopping', 'bills', 'entertainment', 'other'."},
                    "note":     {"type": "string", "description": "Optional note about the expense."},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tiredness",
            "description": "Estimate the user's current tiredness level (0-100%) based on wake time, steps, sleep, and activity.",
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
            "name": "get_todo_list",
            "description": "List all todo items. Returns pending and completed tasks.",
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
            "name": "add_todo",
            "description": "Add a new todo item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text":     {"type": "string", "description": "The todo text."},
                    "priority": {"type": "string", "description": "'low', 'medium', or 'high'."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_todo",
            "description": "Mark a todo item as complete by its ID or number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "Todo ID or number (e.g. '1' for the first todo)."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_prep_note",
            "description": "Save a preparation note for an upcoming conversation. The AI will reference this during the next conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text":  {"type": "string", "description": "The note content."},
                    "topic": {"type": "string", "description": "Topic or context (e.g. 'job interview', 'meeting with client')."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "conversation_summary",
            "description": "Generate an AI summary of the most recent conversation with key points and action items.",
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
            "name": "get_conversation_cue",
            "description": "Get a real-time conversation cue — a suggestion, answer, concept explanation, or bio reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "What's being discussed right now (topic, name, term)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enroll_face",
            "description": (
                "Enroll a person's face into the recognition database using the current camera frame. "
                "Ask the person to look directly at the camera first. "
                "Call multiple times with different photos to improve accuracy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Person's name (e.g. 'Alice', 'Dad')."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_face",
            "description": "Remove a person from the face recognition database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the person to remove."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_known_faces",
            "description": "List all people enrolled in the face recognition database.",
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
            "name": "search_memory",
            "description": (
                "Search your persistent episodic memory for relevant past observations, "
                "conversations, and context. Use when the user asks about something that "
                "may have happened before the current session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory."},
                    "n":     {"type": "integer", "description": "Max results (default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_goals",
            "description": "Display the user's current persistent goals across all domains.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_goal",
            "description": "Set or replace goals for a domain: core, social, professional, romantic, or academic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Goal domain: core | social | professional | romantic | academic"},
                    "items":  {"type": "array",  "items": {"type": "string"}, "description": "List of goal strings."},
                },
                "required": ["domain", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_current_focus",
            "description": "Tell Merlin which goal domain to prioritize in ADVISOR mode right now.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {"type": "string", "description": "Domain name: social, professional, romantic, academic, core."},
                },
                "required": ["focus"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal_note",
            "description": "Add a persistent context note Merlin always considers (e.g. 'going on a date tonight', 'in job negotiation phase').",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "Free-form context note."},
                },
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_profile",
            "description": "Show the user's full skill, strength, and weakness profile.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_strengths",
            "description": "Set the user's strengths list (replaces existing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}, "description": "List of strengths."},
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_weaknesses",
            "description": "Set the user's weaknesses list (replaces existing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "string"}, "description": "List of weaknesses."},
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_skills",
            "description": "Set skills for a domain: professional, social, physical, or other.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Skill domain: professional | social | physical | other"},
                    "items":  {"type": "array", "items": {"type": "string"}, "description": "List of skills."},
                },
                "required": ["domain", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_profile_field",
            "description": "Set a profile text field: personality, communication_style, appearance_notes, triggers, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Field name."},
                    "value": {"type": "string", "description": "Value. For 'triggers', use comma-separated list."},
                },
                "required": ["field", "value"],
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
