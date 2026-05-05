# Merlin

[![GitHub release](https://img.shields.io/github/v/release/ilPez00/merlin?color=%2300e5ff&style=flat-square)](https://github.com/ilPez00/merlin/releases/latest)
[![APK](https://img.shields.io/badge/APK-2.9MB-%2300e5ff?style=flat-square)](https://github.com/ilPez00/merlin/releases/latest/download/merlin.apk)

An always-on AI field intelligence assistant. Your phone becomes a HUD — streaming camera, audio, GPS, and sensors to an AI agent that can see what you see, hear what you hear, and access your tools.

**Standalone or server-connected.** Just an API key and you're running.

---

## Quick install

### Android (signed APK)

Download the latest APK from [GitHub Releases](https://github.com/ilPez00/merlin/releases/latest):

```bash
adb install merlin.apk
```

Or open `merlin.apk` on your phone and enable "Install from unknown sources".

### Desktop / browser

Open `http://localhost:8080/app/` after starting the server, or open `index.html` from any HTTP server.

---

## What it does

### 3 app modes

| Mode | Platform | What you see | What happens |
|---|---|---|---|
| **Visor** | Phone | Camera passthrough + Google Lens-style object labels | Tap to observe surroundings. AI describes what you're looking at. |
| **Copilot** | Phone | Your screen shared + AI observation feed | AI watches your screen periodically, offers guidance and suggestions. |
| **Desktop** | Computer | Screen capture + chat panel | Share your screen, ask questions about what you see. |

### 9 activity modes

Each mode configures sensors, display widgets, and AI behavior:

| Mode | Camera | Audio | GPS | Best for |
|---|---|---|---|---|
| **WORK** | 0.2 fps | ✓ transcribe | off | Desk work, code, files, meetings |
| **LIFT** | 1.0 fps | push-to-talk | off | Gym, rep counting, form tips |
| **WALK** | 0.3 fps | ✓ voice notes | on | Strolling, POI discovery |
| **TALK** | off | ✓ transcribe | off | Conversations, meetings |
| **NOTES** | 0.2 fps | ✓ dictate | on | Journaling, capture ideas |
| **SCOUT** | 0.5 fps | ✓ | on | Environmental awareness |
| **RECON** | 0.1 fps | off | on | Silent data collection |
| **DRIVE** | 0.1 fps | voice cmd | high | Navigation, ETA, traffic |
| **SKI** | 0.5 fps | voice cmd | high | Speed, altitude, trail info |

### Offline diary

All observations, voice notes, photos, and conversations are saved locally in IndexedDB. When your PC server appears on the network, entries sync automatically.

### AI backends

| Backend | Setup |
|---|---|
| **DeepSeek** (default) | Enter API key in the app |
| **OpenAI** | Enter API key, select OpenAI |
| **Anthropic** | Enter API key, select Anthropic |
| **Custom / local** | Enter base URL + API key |

---

## Architecture

```
PHONE (standalone)
  app/ → API key → DeepSeek / OpenAI / Anthropic
  ├── offline diary (IndexedDB)
  └── background sync (when PC server reachable)

PHONE + PC SERVER (full capabilities)
  app/ → WebSocket → server.py → ai/agent.py → LLM
                                     ├── read_file / write_file
                                     ├── run_shell
                                     └── Praxis MCP (goals, diary, scheduler)
```

---

## Project layout

```
merlin/
  app/                  # Cross-platform app (PWA + Android APK)
    index.html          # Entry — setup → picker → mode
    lib/                # Core engine: config, API, camera, screen, audio,
    ui/                 # vision (MediaPipe), diary (IndexedDB), sync
    hud.css / visor.css / copilot.css / desktop.css

  server/               # PC server (Python)
    server.py           # WebSocket server + stdin REPL
    stream_processor.py # Sensor batching, query dispatch

  ai/                   # Agent system
    agent.py            # Tool-use loop
    tools.py            # 15+ tools (read/write files, run shell, Praxis MCP)
    session.py          # Conversation state + backend selection
    system_prompt.txt

  hardware/             # Visor glasses hardware specs
    firmware/           # ESP32-S3 firmware spec
    pcb/                # Shield PCB design
    mechanical/         # 3D-printed frame mount
    bom/                # Bill of materials (~$50)

  start.sh              # Start PC server
  build-apk.sh          # Build Android APK
  VISOR_FUNCTIONS.md    # User-facing spec: activity modes, 7 verbs
```

---

## Build the APK yourself

Requires: Node.js 18+, Java 17+, Android Studio SDK

```bash
./build-apk.sh
adb install merlin.apk
```

---

## Requirements

**Phone (standalone)**
- Android 8+ or any device with Chrome
- An API key (DeepSeek, OpenAI, or Anthropic)

**Server (full agent)**
- Python 3.11+
- An API key
- (Optional) Praxis instance for goal scheduling + diary
