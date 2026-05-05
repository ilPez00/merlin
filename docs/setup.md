# Merlin — Setup Guide

## Prerequisites

- Python 3.11+
- An OpenAI API key (for Whisper transcription + GPT-4o vision)
  - Or set `MERLIN_BASE_URL` to point at a local model server (e.g. Ollama)
- Phone and computer on the same local network

## 1. Install dependencies

```bash
cd merlin
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
```

## 2. Set environment variables

```bash
export OPENAI_API_KEY=sk-...
# Optional overrides:
export MERLIN_PORT=8765
export MERLIN_MODEL=gpt-4o          # or any vision-capable model
# export MERLIN_BASE_URL=http://localhost:11434/v1  # for Ollama
```

## 3. Find your computer's local IP

```bash
ip addr show | grep 'inet ' | grep -v 127
# or on macOS:
ipconfig getifaddr en0
```

Note this IP — you'll enter it in the phone UI.

## 4. Serve the phone PWA

The phone app is a static web page. Serve it over your local network:

```bash
cd merlin/phone
python -m http.server 8080
```

On your phone, open: `http://<your-computer-ip>:8080`

> **HTTPS note**: Some browsers require HTTPS for camera/mic access on non-localhost origins.
> If the browser blocks permissions, use [mkcert](https://github.com/FiloSottile/mkcert) to
> generate a local cert, or use a tool like `caddy` to reverse-proxy with TLS.

## 5. Start the Merlin server

```bash
cd merlin
python -m server.server
```

## 6. Connect

- On your phone browser, open the PWA URL
- Tap **connect** and enter `ws://<your-computer-ip>:8765`
- Grant camera, microphone, and location permissions
- Streaming begins

## Customizing the AI behavior

Edit `ai/system_prompt.txt` to change how Merlin responds — its personality,
what it watches for, what it ignores, etc.

## Using with a local model (Ollama)

```bash
ollama pull llava    # vision-capable model
export MERLIN_BASE_URL=http://localhost:11434/v1
export MERLIN_MODEL=llava
export OPENAI_API_KEY=ollama   # placeholder, required by client
```

Note: local models won't have Whisper for audio — transcription will be skipped
unless you run a separate Whisper server.
