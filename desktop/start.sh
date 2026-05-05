#!/usr/bin/env bash
# ── Merlin Desktop HUD — start-desktop.sh ──────────────────────────
# Launches the transparent overlay HUD for transcriptions,
# translations, navigation, and AI responses.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[merlin-hud] Starting Desktop HUD..."
echo "[merlin-hud] Connect to ws://<server-ip>:8765 when prompted."
echo "[merlin-hud] Ctrl+Shift+H to toggle click-through (mouse interaction)"
echo "[merlin-hud] Ctrl+Shift+Q to quit"
echo ""

npx electron .
