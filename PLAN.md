# Merlin — Jarvis HUD Realization Plan

## Vision

Merlin becomes a Jarvis-like AI assistant using the **PC monitor as a transparent HUD overlay** (like Even Realities G2 glasses, but on any screen). The phone streams sensor data (camera, GPS, audio); the PC server processes everything and pushes live information to both phone panels and the desktop HUD.

## Architecture

```
PHONE (sensors)                 PC SERVER (compute)             PC HUD (transparent overlay)
┌─────────────────┐            ┌──────────────────────┐        ┌──────────────────────────┐
│ Camera + MoveNet│─frames───→│ StreamProcessor      │        │  Electron transparent    │
│ GPS / IMU       │─gps/imu──→│   → rep_counter      │──trans─│  always-on-top window    │
│ Web Speech API  │─audio────→│   → Whisper STT      │──trans─│                          │
│ (wake word +    │─transcr──→│   → translation      │──trans─│  ┌──Nav──────┐┌──AI─────┐│
│  real-time STT) │           │   → OSRM nav          │──nav──→│  │Turn right ││Analyzed ││
│                  │           │   → screen capture    │        │  │on Main St ││your scrn││
│ Slide-in panels:│←─response─│ MerlinSession→Agent   │        │  └───────────┘└─────────┘│
│  exercise/food/ │←─panel_cmd│   → tools             │        │                          │
│  places/goals   │           │   → ~/.merlin/data/   │        │  ┌──Transcription────────┐│
│                  │           │   → Nominatim (places)│        │  │"I think we should..."  ││
└─────────────────┘           └──────────────────────┘        │  └────────────────────────┘│
                                                                │  ┌──Translation──────────┐│
                                                                │  │"Penso che dovremmo..." ││
                                                                │  └────────────────────────┘│
                                                                └──────────────────────────┘
```

## Key Protocol Extensions

### Phone → Server

| Type | Purpose |
|---|---|
| `transcription` | Real-time Web Speech API results (interim/final) forwarded for HUD subtitles |

### Server → All Clients

| Type | Purpose |
|---|---|
| `transcription` | Real-time subtitle text + is_final flag |
| `translation` | `{ original, translated, source_lang, target_lang }` |
| `navigation_update` | `{ instruction, distance_m, turn, lat, lon, summary }` |
| `system_overlay` | `{ text, position, dismiss_after }` — toast notifications on HUD |

## HUD Overlay Layout (Desktop Electron)

```
┌─────────────────────────────────────────────────────────────────┐
│  🧭 NAV              (top-left)         💬 AI     (top-right)  │
│  "Turn right on Main St (200m)"          "3 sets of 10 pushups"│
│                                                                 │
│                                                                 │
│  📝 TRANSCRIPTION (bottom)          🌐 TRANSLATION (bottom)    │
│  "I think we should consider..."     "Penso che dovremmo..."   │
│  "the new approach for scaling"      "il nuovo approccio per..."│
└─────────────────────────────────────────────────────────────────┘
```

- Frame-less, chromeless, transparent background
- Always-on-top, click-through (mouse passes to desktop)
- `Ctrl+Shift+H` to toggle interaction mode
- Corner panels auto-position, dim after inactivity

## New Tools

| Tool | Function | Backend |
|---|---|---|
| `capture_screen()` | Screenshot of PC desktop → base64 | `mss` lib |
| `translate_text(text, target_lang)` | LLM-based translation | Merlin backend |
| `get_navigation(dest_lat, dest_lon)` | Turn-by-turn directions | OSRM + GPS |

## Implementation Phases

### Phase 1 ✓ (Done)

Multi-client server, 12 tools, phone HUD panels, wake word, pose estimation, rep counter, system prompt

### Phase 2 (This sprint)

| # | Component | Files |
|---|---|---|
| 1 | Electron desktop HUD | `desktop/` (5 files) |
| 2 | Screen capture tool | `ai/tools.py`, `server/requirements.txt` |
| 3 | Translation tool | `ai/tools.py`, `ai/system_prompt.txt` |
| 4 | Navigation tool | `ai/tools.py` + OSRM API |
| 5 | Real-time transcription stream | `app/hud.js`, `server/stream_processor.py` |
| 6 | Translation module | `server/translate.py` |

### Phase 3 (Future)

- Voice-controlled HUD layout ("move nav to bottom-right")
- Multi-monitor support
- Eye tracking for attention-aware HUD
- G2 glasses API integration (hardware)
- Smart ring integration (phone accelerometer as gesture input)

## Data Storage

All user data in `~/.merlin/data/` as JSON:

| File | Contents |
|---|---|
| `user_profile.json` | Name, age, weight, goals, preferences |
| `exercise_log.json` | [{timestamp, exercise, reps, sets}] |
| `food_log.json` | [{timestamp, food, calories, macros}] |
| `places.json` | [{name, lat, lon, category}] |
| `action_items.json` | [{timestamp, item, done}] |
