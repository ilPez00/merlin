# CLAUDE.md — Merlin Developer Notes

## Project overview

Merlin is an always-on AI field-intelligence assistant. A phone runs a full-screen HUD (Capacitor Android APK, served from `app/`), streams camera frames, audio, GPS, and IMU data over WebSocket to a Python server on the PC. The server feeds the data into an agentic AI session that can read/write PC files and execute shell commands.

## How to run

```bash
# 1. Start the server (creates venv, installs deps, prints QR code)
./start.sh

# 2. Open the HUD in a browser OR install the APK (see below)
#    http://<LAN-IP>:8080

# 3. Build the Android APK
./build-apk.sh        # produces merlin.apk
adb install merlin.apk
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MERLIN_API_KEY` | — | API key (any backend) |
| `OPENAI_API_KEY` | — | OpenAI / DeepSeek key |
| `ANTHROPIC_API_KEY` | — | Claude key (auto-selects Anthropic backend) |
| `MERLIN_BACKEND` | auto | `openai` or `anthropic` |
| `MERLIN_BASE_URL` | — | Custom OpenAI-compat endpoint (e.g. DeepSeek, Ollama) |
| `MERLIN_MODEL` | `deepseek-chat` | Model name |
| `MERLIN_PORT` | `8765` | WebSocket server port |
| `MERLIN_HTTP_PORT` | `8080` | HUD HTTP server port |

DeepSeek example:
```bash
export MERLIN_API_KEY=sk-...
export MERLIN_BASE_URL=https://api.deepseek.com
export MERLIN_MODEL=deepseek-chat
./start.sh
```

## Project structure

```
merlin/
  app/                  # Phone HUD (Capacitor web app)
    index.html          # Full-screen camera shell + overlaid UI
    hud.js              # All phone logic: WS, streaming, modes, rendering
    hud.css             # HUD styling; --mode-color drives all accents

  server/
    server.py           # WebSocket server + stdin REPL
    stream_processor.py # Batches sensor data, triggers agent queries
    requirements.txt

  ai/
    agent.py            # Agentic tool-use loop (backend-agnostic)
    tools.py            # 5 tools: read_file, write_file, list_dir, run_shell, read_phone_file
    session.py          # Conversation state, backend selection, push_context / query / auto_observe
    system_prompt.txt   # Merlin persona + mode descriptions
    backends/
      openai_compat.py  # OpenAI / DeepSeek / Ollama
      anthropic_backend.py  # Claude via Anthropic SDK

  phone/                # Old PWA (kept for reference; superseded by app/)
  docs/setup.md
  capacitor.config.json
  package.json
  start.sh              # Server start script
  build-apk.sh          # Android APK build script
```

## HUD modes

| Mode | Color | Frame Hz | Audio | GPS | Auto-observe | Purpose |
|---|---|---|---|---|---|---|
| SCOUT | `#00e5ff` | 0.5 | ✓ | ✓ | 15 s | Environmental awareness |
| NAV | `#00e676` | 0.2 | — | ✓ | 30 s | GPS / location context |
| ANALYZE | `#ffab40` | 1.0 | — | — | tap | Deep visual analysis |
| LISTEN | `#e040fb` | 0.1 | ✓ | — | 10 s | Audio transcription |
| QUERY | `#ff6e40` | 0.5 | ✓ | ✓ | — | Agent Q&A with file tools |
| RECON | `#546e7a` | 0.1 | — | ✓ | — | Silent collection |

## WebSocket protocol

**Phone → Server (JSON)**
- `{type:"query", text, mode}` — explicit user question
- `{type:"observe", mode}` — trigger proactive observation
- `{type:"mode_change", mode}` — mode switch notification
- `{type:"file_content", path, content}` — response to `request_file`
- `{type:"imu", ax,ay,az,gx,gy,gz, ts}`
- `{type:"gps", lat,lon,alt,acc,speed, ts}`

**Phone → Server (binary)**
- `JSON_header\nBLOB` where header `{type:"frame"|"audio", ts, mode}`

**Server → Phone (JSON)**
- `{type:"response", text, mode}` — AI response
- `{type:"status", connected, model}` — on connect
- `{type:"request_file", path}` — agent requesting phone file

## Agent tools

The agent (QUERY mode or PC stdin) can call:
- `read_file(path)` — read any PC file (≤ 64 KB)
- `write_file(path, content)` — write/create a file
- `list_dir(path)` — list directory contents
- `run_shell(cmd)` — run a shell command (30 s timeout; blocks catastrophic patterns)
- `read_phone_file(path)` — requests the file from the phone over WebSocket

## Backend selection logic

```
MERLIN_BACKEND=anthropic  → AnthropicBackend (Claude)
ANTHROPIC_API_KEY set     → AnthropicBackend (auto)
otherwise                 → OpenAICompatBackend (OpenAI / DeepSeek / Ollama)
```

## Key design notes

- `server/server.py` runs as `python -m server.server` from the project root, so it uses relative imports for `server.*` and absolute imports for `ai.*`.
- `ai/agent.py` keeps messages in OpenAI format internally. `anthropic_backend.py` converts them (including `tool_calls` on assistant messages) before sending to the Anthropic API.
- Phone file access requires user interaction: the server sends `request_file`, the HUD pops a native file picker, the user selects the file, content is sent back.
- `ai/tools.py` exposes a `set_phone_sender(fn)` / `resolve_phone_file(path, content)` pair that the server calls to wire up the phone-file relay.
