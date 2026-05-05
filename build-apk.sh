#!/usr/bin/env bash
# ── Merlin — build-apk.sh ─────────────────────────────────────────────────────
# Builds the Merlin Android APK using Capacitor + the system Android SDK.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}[build]${RESET} $*"; }
ok()    { echo -e "${GREEN}[build]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[build]${RESET} $*"; }
error() { echo -e "${RED}[build]${RESET} $*" >&2; exit 1; }

# ── 1. Detect ANDROID_HOME ────────────────────────────────────────────────────
info "Detecting Android SDK…"

ANDROID_HOME="${ANDROID_HOME:-}"

if [[ -z "$ANDROID_HOME" ]]; then
    # Common install locations
    for candidate in \
        "$HOME/Android/Sdk" \
        "$HOME/android-sdk" \
        "/opt/android-sdk" \
        "/usr/local/lib/android/sdk"
    do
        if [[ -d "$candidate" ]]; then
            ANDROID_HOME="$candidate"
            break
        fi
    done
fi

# Try Android Studio's bundled SDK
if [[ -z "$ANDROID_HOME" ]]; then
    for studio_sdk in \
        "$HOME/.local/share/Android/Sdk" \
        "$HOME/Library/Android/sdk"
    do
        if [[ -d "$studio_sdk" ]]; then
            ANDROID_HOME="$studio_sdk"
            break
        fi
    done
fi

[[ -z "$ANDROID_HOME" ]] && error "Android SDK not found. Set ANDROID_HOME or install Android Studio."
export ANDROID_HOME
ok "ANDROID_HOME=${ANDROID_HOME}"

# Ensure build-tools and platform-tools are in PATH
export PATH="${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/tools/bin:${PATH}"

# ── 2. Check Node.js ≥ 18 ────────────────────────────────────────────────────
info "Checking Node.js…"
NODE=$(command -v node || true)
[[ -z "$NODE" ]] && error "Node.js not found. Install Node.js 18+."
NODE_VER=$(node --version | sed 's/v//')
NODE_MAJ=$(echo "$NODE_VER" | cut -d. -f1)
[[ "$NODE_MAJ" -lt 18 ]] && error "Node.js 18+ required (found v${NODE_VER})"
ok "Node.js v${NODE_VER}"

# ── 3. Check Java ≥ 17 ────────────────────────────────────────────────────────
info "Checking Java…"
JAVA=$(command -v java || true)
[[ -z "$JAVA" ]] && error "Java not found. Install JDK 17+."
JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/{print $2}' | cut -d. -f1)
[[ -z "$JAVA_VER" ]] && JAVA_VER=$(java -version 2>&1 | grep -oP '\d+' | head -1)
[[ "${JAVA_VER:-0}" -lt 17 ]] && error "Java 17+ required (found ${JAVA_VER})"
ok "Java ${JAVA_VER}"

# ── 4. npm install ────────────────────────────────────────────────────────────
info "Installing npm dependencies…"
npm install --silent
ok "npm install done"

# ── 5. Add Android platform (if not already present) ──────────────────────────
if [[ ! -d "android" ]]; then
    info "Adding Android platform…"
    npx cap add android
    ok "Android platform added"
else
    ok "Android platform already present"
fi

# ── 6. Patch AndroidManifest.xml ──────────────────────────────────────────────
MANIFEST="android/app/src/main/AndroidManifest.xml"
info "Patching AndroidManifest.xml…"

# Add permissions before </manifest> if not already there
add_permission() {
    local perm="$1"
    if ! grep -q "$perm" "$MANIFEST"; then
        sed -i "s|</manifest>|    <uses-permission android:name=\"${perm}\" />\n</manifest>|" "$MANIFEST"
        info "  + ${perm}"
    fi
}

add_permission "android.permission.CAMERA"
add_permission "android.permission.RECORD_AUDIO"
add_permission "android.permission.INTERNET"
add_permission "android.permission.ACCESS_FINE_LOCATION"
add_permission "android.permission.ACCESS_COARSE_LOCATION"
add_permission "android.permission.BODY_SENSORS"

# Add networkSecurityConfig attribute to <application> tag if not present
if ! grep -q "networkSecurityConfig" "$MANIFEST"; then
    sed -i 's|<application|<application\n        android:networkSecurityConfig="@xml/network_security_config"|' "$MANIFEST"
    info "  + networkSecurityConfig attribute"
fi

ok "AndroidManifest.xml patched"

# ── 7. Write network_security_config.xml ──────────────────────────────────────
NET_SEC_DIR="android/app/src/main/res/xml"
NET_SEC_FILE="${NET_SEC_DIR}/network_security_config.xml"
info "Writing network security config…"
mkdir -p "$NET_SEC_DIR"
cat > "$NET_SEC_FILE" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<!--
  Merlin — allow cleartext WebSocket connections to LAN addresses.
  This is intentional: the server runs on the local network without TLS.
-->
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.0.0</domain>
        <domain includeSubdomains="true">192.168.1.0</domain>
        <domain includeSubdomains="true">10.0.0.0</domain>
        <domain includeSubdomains="true">172.16.0.0</domain>
    </domain-config>
    <base-config cleartextTrafficPermitted="true" />
</network-security-config>
XML
ok "network_security_config.xml written"

# ── 8. Capacitor sync ─────────────────────────────────────────────────────────
info "Running npx cap sync…"
npx cap sync android
ok "cap sync complete"

# ── 9. Build debug APK ────────────────────────────────────────────────────────
info "Building debug APK (this may take a few minutes)…"
cd android
chmod +x gradlew
./gradlew assembleDebug --quiet
cd "$SCRIPT_DIR"
ok "Build complete"

# ── 10. Copy APK to project root ──────────────────────────────────────────────
APK_SRC=$(find android/app/build/outputs/apk/debug -name "*.apk" | head -1)
if [[ -z "$APK_SRC" ]]; then
    error "APK not found in android/app/build/outputs/apk/debug/"
fi

cp "$APK_SRC" merlin.apk
ok "APK copied to: ${SCRIPT_DIR}/merlin.apk"

APK_SIZE=$(du -sh merlin.apk | cut -f1)

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  Build successful! APK: merlin.apk (${APK_SIZE})${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  Install options:"
echo ""
echo -e "  ${CYAN}Option A — USB (adb):${RESET}"
echo "    adb install merlin.apk"
echo ""
echo -e "  ${CYAN}Option B — Wi-Fi sideload:${RESET}"
echo "    1. Copy merlin.apk to your phone"
echo "    2. Enable 'Install from unknown sources' in Settings"
echo "    3. Open the APK file and install"
echo ""
echo -e "  ${CYAN}Option C — Android Studio:${RESET}"
echo "    Drag merlin.apk onto a connected emulator or device"
echo ""
