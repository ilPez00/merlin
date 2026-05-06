# Merlin — Development Roadmap

**Mission:** Provide easy integration with technology and guide the user into their best possible life.

**10,450 LOC · 41 tools · 12 widgets · 9 modes · 4 platform clients**

---

## Completed Foundation

| Layer | Status |
|---|---|
| Agent engine (41 tools, tool loop, 3 backends) | ✅ |
| Desktop TUI (voice pipeline, sudo, TTS, mic test, settings) | ✅ |
| Phone PWA/APK (Visor, Copilot, Desktop modes, camera, lens) | ✅ |
| Phone app standalone + background sync to PC server | ✅ |
| Audio pipeline (RingBuffer, Whisper, wake word, storage, weekly cleanup) | ✅ |
| Context strip (12 widgets, per-mode config, tiredness heuristic) | ✅ |
| Voice command parser ("up/down/show/switch", 16 patterns) | ✅ |
| Even G2 features (Prep Notes, Conversation Summary, AI Cues, Memory) | ✅ |
| Proactive advisor (30-min LLM tips from todos, expenses, tiredness) | ✅ |
| Dossier system (LLM-built profiles for people/places/events/activities, Ctrl+D export) | ✅ |
| Conversation logging (~/.merlin/conversations.md) | ✅ |
| Behavioral cues (name recall, follow-up detection, topic bridges, compliment triggers) | ✅ |
| Hardware specs (ESP32-S3 firmware, PCB, mechanical, BOM, ~$50) | ✅ |
| Android APK (signed release, 2.9MB, GitHub Releases) | ✅ |

---

## Architecture: MCP-first integrations

Merlin does NOT hardcode integrations. Instead, it's an **MCP (Model Context Protocol) client**. Users configure MCP servers in Settings, and the agent discovers their tools dynamically at runtime.

```
User configures in Settings:
┌─────────────────────────────────────┐
│  MCP Servers                         │
│                                      │
│  ☑ Praxis (local)                    │
│     URL: http://localhost:3001       │
│                                      │
│  ☑ Google Calendar                   │
│     Status: Connected (OAuth)        │
│                                      │
│  ☐ Fitbit                            │
│     Status: Disconnected             │
│                                      │
│  [+ Add MCP Server]                  │
└─────────────────────────────────────┘

At runtime:
  agent discovers tools from all connected MCP servers
  tools appear alongside read_file, run_shell, etc.
```

| MCP server | Provides tools for | Auth |
|---|---|---|
| **Praxis** | goals, diary, schedule, trackers | API key |
| **Google Calendar** | events, calendar queries | OAuth (browser) |
| **OpenWeather** | weather at GPS | API key |
| **Fitbit** | steps, sleep, HR, active minutes | OAuth (browser) |
| **Yazio** | calories, meals, macros | API key |
| **Revolut** | transactions, spending | API key |
| **Resend / SendGrid** | send email | API key |

All OAuth flows: **open browser → user authorizes → token saved to `~/.merlin/integrations/`**. No manual token copy-paste.

---

## Phase A — Connected Merlin (~5 days)

Integrations that fill empty widgets and connect to real services.

### A1 — MCP client
- `ai/mcp/client.py` — connects to MCP servers, discovers tools, calls tools
- `ai/mcp/registry.py` — manages server list, health checks, reconnection
- Settings screen: add/remove MCP servers, test connection, view tools

### A2 — MCP servers (built-in)
- `ai/mcp/servers/weather.py` — OpenWeather (API key, no OAuth)
- `ai/mcp/servers/calendar.py` — Google Calendar (OAuth, browser)
- `ai/mcp/servers/email.py` — Resend/SendGrid (API key)
- Each server is a standalone script that implements the MCP protocol

### A3 — Praxis MCP server
- `ai/mcp/servers/praxis.py` — connects to Praxis backend
- Tools: `get_goals`, `log_diary_entry`, `get_schedule`, `get_progress`
- Syncs local diary entries to Praxis notebook
- Fills `schedule` widget with next time slot
- Auto-switches activity mode based on schedule

### A4 — Widget data flow
- Widgets now pull from MCP servers instead of `ai/widgets.py` runtime
- `weather` → OpenWeather MCP
- `next_event` → Google Calendar MCP
- `cal_burned` → Fitbit MCP
- `cal_consumed` → Yazio MCP
- `money_spent` → Revolut MCP
- Fall back to heuristic/empty if server is disconnected

---

## Phase B — Memory & Planning (~5 days)

Persistent semantic memory and proactive life planning.

### B1 — ChromaDB persistent memory
- Replace `ai/memory.py` JSON stubs with ChromaDB
- Embed every conversation entry, diary entry, and tool result
- `memory_search()` returns semantically relevant past context
- Dossier LLM prompts include relevant memory chunks

### B2 — Axiom daily schedule
- Pull daily schedule from Praxis MCP
- Show next time slot in context strip with countdown
- Auto-switch mode based on schedule activity type
- Advisor warns before schedule transitions

### B3 — Health dashboard (via MCP)
- Fitbit: steps, sleep HR, active minutes
- Yazio: calories consumed, meals
- Tiredness heuristic uses real sleep/activity data

### B4 — Finance dashboard (via MCP)
- Revolut: daily transactions, spending by category
- Auto-fills `money_spent` widget
- Advisor flags spending patterns

---

## Phase C — Daily Driver (~5 days)

Polish, offline mode, production readiness.

### C1 — Daemon mode
- `desktop/daemon.py` — runs without TUI, tray icon
- OS notifications for wake word, advisor tips, meeting alerts
- Voice pipeline stays active, responses as notifications

### C2 — Face recognition
- Wire `vision/face_recognizer.py` into dossier system
- When camera detects known face, auto-tags conversation with that person
- Dossier gets meeting timestamp and duration

### C3 — Local LLM (Ollama)
- `ai/backends/ollama.py` — OpenAI-compat wrapper
- Fully offline operation
- Settings toggle: cloud / local / hybrid

### C4 — Voice activity detection
- Silero VAD before Whisper transcription
- Only runs Whisper when speech detected
- Reduces CPU ~10x

### C5 — TUI polish
- Connection status indicator per MCP server
- Crash recovery / auto-restart
- First-run setup wizard (API key, wake word, mic test)
- Error notifications in OS notification center

---

## Phase D — Hardware Visor (~2 weeks)

### D1 — Prototype
- Order XIAO ESP32S3 Sense + components (~$50 BOM)
- Firmware: WiFi + WebSocket handshake
- Add OLED display, encoder, IMU
- 3D print Wayfarer frame mount
- Test continuous voice + camera streaming to PC server

### D2 — Custom PCB
- Design shield PCB (KiCad)
- Order from JLCPCB
- Assemble and test

### D3 — Production frame
- Magnesium frame design (injection mold)
- Micro-OLED waveguide display
- Charging case (7 charges)
- BLE ring input

---

## MCP Server Development Order

| Server | Phase | Auth | Widgets filled |
|---|---|---|---|
| OpenWeather | A2 | API key | `weather` |
| Google Calendar | A2 | OAuth | `next_event` |
| Email (Resend) | A2 | API key | — |
| Praxis | A3 | API key | `schedule` |
| Fitbit | B3 | OAuth | `steps`, `cal_burned`, `sleep_hours` |
| Yazio | B3 | API key | `cal_consumed` |
| Revolut | B4 | API key | `money_spent` |

---

## Key decisions

| Decision | Choice |
|---|---|
| Phase order | A → B → C → D |
| MCP architecture | User-configured servers, agent discovers tools dynamically |
| OAuth flow | Open browser for everything, local callback server on random port |
| Default provider | DeepSeek (user can change in settings) |
| Voice pipeline | Push-to-talk + wake word ("marlin"/"merlino"/user-set) |
| TTS voice | edge-tts JennyNeural (user-changeable in settings) |
| Conversation storage | Single file: ~/.merlin/conversations.md |
| Dossier export | ~/.merlin/dossiers.md (Ctrl+D) |
| Widget limit | 4 per mode context strip |
