#!/usr/bin/env bash
# ── Merlin — start.sh ─────────────────────────────────────────────────────────
# Sets up the Python venv, installs deps, prints the QR code, and starts
# the WebSocket server + HTTP file server for the HUD app.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
SERVER_PORT="${MERLIN_PORT:-8765}"
HTTP_PORT="${MERLIN_HTTP_PORT:-8080}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}[merlin]${RESET} $*"; }
ok()    { echo -e "${GREEN}[merlin]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[merlin]${RESET} $*"; }
error() { echo -e "${RED}[merlin]${RESET} $*" >&2; exit 1; }

# ── Python version check ──────────────────────────────────────────────────────
info "Checking Python version…"
PYTHON=$(command -v python3 || command -v python || true)
[[ -z "$PYTHON" ]] && error "Python not found. Install Python 3.11+."

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11) ]]; then
    error "Python 3.11+ required (found $PY_VERSION)"
fi
ok "Python $PY_VERSION"

# ── Virtual environment ───────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment…"
    "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "venv activated"

# ── Install dependencies ──────────────────────────────────────────────────────
info "Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r server/requirements.txt
ok "Dependencies installed"

# ── Detect LAN IP ─────────────────────────────────────────────────────────────
detect_ip() {
    # Try common methods in order
    local ip

    # 1. ip route (Linux)
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
    [[ -n "$ip" ]] && echo "$ip" && return

    # 2. hostname -I (Linux)
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    [[ -n "$ip" ]] && echo "$ip" && return

    # 3. macOS ifconfig
    ip=$(ifconfig 2>/dev/null | awk '/inet /{if($2!="127.0.0.1") print $2}' | head -1)
    [[ -n "$ip" ]] && echo "$ip" && return

    echo "127.0.0.1"
}

LAN_IP=$(detect_ip)
export MERLIN_SERVER_IP="$LAN_IP"

WS_URL="ws://${LAN_IP}:${SERVER_PORT}"
HTTP_URL="http://${LAN_IP}:${HTTP_PORT}"

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  MERLIN AI Field Intelligence${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  WebSocket : ${CYAN}${WS_URL}${RESET}"
echo -e "  HUD App   : ${CYAN}${HTTP_URL}${RESET}"
echo ""

# ── Print QR code ─────────────────────────────────────────────────────────────
info "Scan this QR code on your phone to open the HUD:"
"$PYTHON" - <<PYEOF
import sys
try:
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data("${HTTP_URL}")
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print()
    print("  Then enter the WebSocket URL: ${WS_URL}")
    print()
except ImportError:
    print("  (install qrcode[pil] for QR code display)")
    print("  Phone URL: ${HTTP_URL}")
    print("  WS URL:    ${WS_URL}")
PYEOF

# ── Start HTTP server for HUD app (background) ────────────────────────────────
info "Starting HUD HTTP server on port ${HTTP_PORT}…"
"$PYTHON" -m http.server "$HTTP_PORT" --directory app --bind 0.0.0.0 \
    >/tmp/merlin_http.log 2>&1 &
HTTP_PID=$!
ok "HTTP server PID ${HTTP_PID} → ${HTTP_URL}"

# ── Trap to clean up background processes on exit ─────────────────────────────
cleanup() {
    echo ""
    info "Shutting down…"
    kill "$HTTP_PID" 2>/dev/null || true
    deactivate 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Start WebSocket server (foreground) ───────────────────────────────────────
echo ""
echo -e "${BOLD}Starting Merlin server…${RESET}"
echo -e "  Type a query and press ${BOLD}Enter${RESET} to ask Merlin from this terminal."
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop."
echo ""

exec python -m server.server
