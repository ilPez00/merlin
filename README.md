# Merlin

An always-on AI field intelligence assistant. Your phone becomes a HUD — streaming camera, audio, GPS, and sensors to an AI agent running on your PC that can see what you see, hear what you hear, and access your files.

> Named after the wizard, not the bird (though the bird is also fast).

---

## What it does

- **Full-screen phone HUD** with 6 contextual modes (SCOUT, NAV, ANALYZE, LISTEN, QUERY, RECON)
- **Streams** live camera frames, microphone audio, GPS, and IMU data from phone to PC over WebSocket
- **Agentic AI** with tool use: reads/writes PC files, runs shell commands, requests phone files on demand
- **Pluggable backends**: DeepSeek, OpenAI, Claude (Anthropic), or any OpenAI-compatible API
- **Android APK** built via Capacitor — no app store needed

---

## Quick start

### 1. Start the server

```bash
# Set your API key (DeepSeek example)
export MERLIN_API_KEY=sk-...
export MERLIN_BASE_URL=https://api.deepseek.com
export MERLIN_MODEL=deepseek-chat

./start.sh
```

This creates a venv, installs dependencies, detects your LAN IP, prints a QR code, and starts both the WebSocket server (`:8765`) and a static file server for the HUD (`:8080`).

### 2. Connect your phone

- Scan the QR code or open `http://<your-ip>:8080` in Chrome on Android
- Enter the WebSocket URL shown in the terminal and tap **CONNECT**
- Grant camera, microphone, and location permissions

### 3. (Optional) Install as a native APK

```bash
./build-apk.sh        # requires Android Studio SDK + Node.js 18+ + Java 17+
adb install merlin.apk
```

---

## HUD modes

| Mode | Accent | Auto-observe | Purpose |
|---|---|---|---|
| **SCOUT** | cyan | every 15 s | Environmental awareness |
| **NAV** | green | every 30 s | GPS / location context |
| **ANALYZE** | amber | tap to trigger | Deep visual analysis |
| **LISTEN** | purple | every 10 s | Audio transcription |
| **QUERY** | orange | off | Agent Q&A — ask anything, uses file tools |
| **RECON** | slate | off | Silent collection, minimal HUD |

In **QUERY** mode you can type a question on the phone or from the PC terminal — the agent will use tools to answer (e.g. read a file, run `git log`, check a directory).

---

## AI backends

| Backend | How to select |
|---|---|
| **DeepSeek** (default) | Set `MERLIN_BASE_URL=https://api.deepseek.com` + `MERLIN_MODEL=deepseek-chat` |
| **OpenAI** | Set `OPENAI_API_KEY`, leave `MERLIN_BASE_URL` unset |
| **Claude** | Set `ANTHROPIC_API_KEY` (auto-detected) or `MERLIN_BACKEND=anthropic` |
| **Ollama / local** | Set `MERLIN_BASE_URL=http://localhost:11434/v1` + `MERLIN_MODEL=llava` |

---

## Agent tools

When you ask a question in QUERY mode, the AI can:

| Tool | What it does |
|---|---|
| `read_file(path)` | Read any file on the PC (up to 64 KB) |
| `write_file(path, content)` | Create or overwrite a file |
| `list_dir(path)` | List directory contents |
| `run_shell(cmd)` | Run a shell command and return output |
| `read_phone_file(path)` | Ask the phone to send a file (triggers a file picker) |

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Phone HUD (Android / Chrome)            │
│  ┌──────────────────────────────────┐    │
│  │ Camera  Audio  GPS  IMU          │    │
│  │ 6 modes: SCOUT NAV ANALYZE …     │    │
│  └─────────────┬────────────────────┘    │
└────────────────│────────────────────────┘
                 │ WebSocket (LAN)
                 │ frames / audio / JSON
┌────────────────▼────────────────────────┐
│  Merlin Server (Python)                  │
│  stream_processor.py  ←  batches data    │
│  server.py  ←  stdin REPL               │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  AI Agent (ai/)                          │
│  session.py → agent.py → tools.py        │
│  backends: OpenAI-compat / Anthropic     │
└─────────────────────────────────────────┘
```

---

## Project layout

```
merlin/
  app/                  # Phone HUD (Capacitor web app)
    index.html          # Full-screen camera shell
    hud.js              # WebSocket, modes, streaming, rendering
    hud.css             # --mode-color CSS variable + HUD chrome

  server/
    server.py           # WebSocket server, stdin REPL
    stream_processor.py # Sensor batching, query/observe dispatch
    requirements.txt

  ai/
    agent.py            # Agentic tool-use loop
    tools.py            # read_file, write_file, list_dir, run_shell, read_phone_file
    session.py          # Conversation state + backend selection
    system_prompt.txt
    backends/
      openai_compat.py
      anthropic_backend.py

  start.sh              # Server start + QR code
  build-apk.sh          # Android APK build
  capacitor.config.json
  package.json
  CLAUDE.md             # Developer notes for AI assistants
```

---

## Requirements

**Server (PC)**
- Python 3.11+
- An API key for DeepSeek / OpenAI / Anthropic (or a local Ollama instance)

**APK build**
- Node.js 18+
- Java 17+
- Android Studio (for the SDK; `ANDROID_HOME` must be set or auto-detected)

**Phone**
- Android with Chrome, or the installed Merlin APK
- Camera, microphone, and location permissions
