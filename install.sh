#!/bin/bash
# install.sh — Vashishtha Installer
# Handles everything: pkg, custom wheels, pip, sandbox, va binary, config

set -e

VASHISHTHA_DIR="$(cd "$(dirname "$0")" && pwd)"
WHEEL_BASE="https://github.com/krnova/android-wheels/releases/download"

# ── Colors ────────────────────────────────────────────────────────────────────
GOLD='\033[38;5;220m'
DIM='\033[2m'
GREEN='\033[38;5;82m'
RED='\033[38;5;196m'
ORANGE='\033[38;5;208m'
BLUE='\033[38;5;75m'
RESET='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────

step() { printf "\n${GOLD}▸ $1${RESET}\n"; }
ok()   { printf "  ${GREEN}✓${RESET} $1\n"; }
skip() { printf "  ${DIM}↷ $1 (already installed)${RESET}\n"; }
fail() { printf "  ${RED}✗ $1${RESET}\n"; }
info() { printf "  ${DIM}$1${RESET}\n"; }

pkg_installed() { pkg list-installed 2>/dev/null | grep -q "^$1/"; }
pip_installed() { pip show "$1" &>/dev/null; }
cmd_exists()    { command -v "$1" > /dev/null 2>&1; }

# ── Header ────────────────────────────────────────────────────────────────────

clear
printf "${GOLD}"
printf "┌─────────────────────────────────────────┐\n"
printf "│       वशिष्ठ — Vashishtha                │\n"
printf "│       Installer                         │\n"
printf "└─────────────────────────────────────────┘\n"
printf "${RESET}\n"

# ── Step 1: Termux packages ───────────────────────────────────────────────────

step "Termux packages"

PKG_PACKAGES=(python python-cryptography rust proot-distro git jq)

pkg update -y -q 2>/dev/null || true

for p in "${PKG_PACKAGES[@]}"; do
    if pkg_installed "$p"; then
        skip "$p"
    else
        info "Installing $p..."
        pkg install -y "$p" -q 2>/dev/null && ok "$p" || fail "$p"
    fi
done

# termux-api — optional
printf "\n  ${BLUE}Install termux-api?${RESET} ${DIM}(enables SMS, camera, GPS, clipboard, TTS)${RESET} [y/N] "
read -r install_api
if [[ "$install_api" =~ ^[Yy]$ ]]; then
    if pkg_installed "termux-api"; then
        skip "termux-api"
    else
        pkg install -y termux-api -q 2>/dev/null && ok "termux-api" || fail "termux-api"
    fi
else
    info "Skipping termux-api — device tools will be unavailable"
fi

# ── Step 2: Android-specific wheels ──────────────────────────────────────────

step "Android ARM64 wheels (pydantic-core, jiter)"
info "These are pre-built for Python 3.13 + Android ARM64"
info "Standard pip wheels won't work on this platform"

WHEELS=(
    "$WHEEL_BASE/v2.41.5-android/pydantic_core-2.41.5-cp313-cp313-android_arm64_v8a.whl"
    "$WHEEL_BASE/v0.13.0-android/jiter-0.13.0-cp313-cp313-android_arm64_v8a.whl"
)

for wheel in "${WHEELS[@]}"; do
    name=$(basename "$wheel" | cut -d- -f1)
    if pip_installed "$name"; then
        skip "$name"
    else
        info "Installing $name..."
        pip install --break-system-packages -q "$wheel" 2>/dev/null && ok "$name" || fail "$name"
    fi
done

# ── Step 3: Python packages ───────────────────────────────────────────────────

step "Python packages"

PIP_PACKAGES=(
    flask
    python-dotenv
    "google-genai>=1.0.0"
    openai
    requests
    beautifulsoup4
    python-dateutil
)

for pkg in "${PIP_PACKAGES[@]}"; do
    # strip version specifiers to get the install name
    bare=$(echo "$pkg" | sed 's/[>=<].*//')
    # pip show uses the package name (with hyphens), import check is unreliable for namespaced packages
    if pip_installed "$bare"; then
        skip "$pkg"
    else
        info "Installing $pkg..."
        pip install --break-system-packages --prefer-binary -q "$pkg" 2>/dev/null && ok "$pkg" || fail "$pkg"
    fi
done

# ── Step 4: Sandbox (Alpine via proot-distro) ─────────────────────────────────

step "Sandbox — Alpine Linux (proot-distro)"

ALPINE_ROOTFS="$PREFIX/var/lib/proot-distro/installed-rootfs/alpine"

if [ -d "$ALPINE_ROOTFS" ]; then
    skip "Alpine already installed"
else
    info "Installing Alpine Linux (~150MB)..."
    proot-distro install alpine && ok "Alpine installed" || { fail "Alpine install failed"; exit 1; }
fi

info "Installing sandbox languages (python3, nodejs, openjdk17)..."
proot-distro login alpine -- sh -c "
    apk update -q
    for p in python3 nodejs openjdk17; do
        if apk info -e \$p >/dev/null 2>&1; then
            printf '  \033[2m↷ %s (already installed)\033[0m\n' \$p
        else
            apk add -q \$p && printf '  \033[38;5;82m✓\033[0m %s\n' \$p || printf '  \033[38;5;196m✗\033[0m %s\n' \$p
        fi
    done
"

# ── Step 5: va CLI binary ─────────────────────────────────────────────────────

step "va CLI binary"

if [ ! -f "$VASHISHTHA_DIR/va" ]; then
    fail "va binary not found in $VASHISHTHA_DIR"
elif [ -f "$PREFIX/bin/va" ]; then
    skip "va already in \$PREFIX/bin"
else
    cp "$VASHISHTHA_DIR/va" "$PREFIX/bin/va"
    chmod +x "$PREFIX/bin/va"
    ok "va installed to \$PREFIX/bin/va"
fi

# ── Step 6: Config files ──────────────────────────────────────────────────────

step "Configuration"

if [ -f "$VASHISHTHA_DIR/config.json" ]; then
    skip "config.json already exists"
else
    cp "$VASHISHTHA_DIR/config.example.json" "$VASHISHTHA_DIR/config.json"
    ok "config.json created from example"
fi

if [ -f "$VASHISHTHA_DIR/.env" ]; then
    skip ".env already exists"
else
    cp "$VASHISHTHA_DIR/.env.example" "$VASHISHTHA_DIR/.env"
    ok ".env created from example"
fi

# ── Step 7: API key setup ─────────────────────────────────────────────────────

step "API Key Setup"

ENV_FILE="$VASHISHTHA_DIR/.env"

printf "\n  Which provider do you want to use?\n"
printf "  ${GREEN}1${RESET} NIM   (NVIDIA — default, supports thinking mode)\n"
printf "  ${GREEN}2${RESET} Gemini (Google)\n"
printf "  ${GREEN}3${RESET} Groq  (fast inference)\n"
printf "  ${DIM}0  Skip — I'll edit .env manually${RESET}\n"
printf "\n  Choice [1]: "
read -r provider_choice
provider_choice="${provider_choice:-1}"

case "$provider_choice" in
    1)
        printf "  NIM API key: "
        read -r api_key
        if [ -n "$api_key" ]; then
            sed -i "s/NIM_API_KEY=.*/NIM_API_KEY=$api_key/" "$ENV_FILE"
            python3 -c "
import json
with open('$VASHISHTHA_DIR/config.json') as f: c = json.load(f)
c['api']['provider'] = 'nim'
with open('$VASHISHTHA_DIR/config.json', 'w') as f: json.dump(c, f, indent=2)
"
            ok "NIM key saved, provider set to nim"
        fi
        ;;
    2)
        printf "  Gemini API key: "
        read -r api_key
        if [ -n "$api_key" ]; then
            sed -i "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$api_key/" "$ENV_FILE"
            python3 -c "
import json
with open('$VASHISHTHA_DIR/config.json') as f: c = json.load(f)
c['api']['provider'] = 'gemini'
with open('$VASHISHTHA_DIR/config.json', 'w') as f: json.dump(c, f, indent=2)
"
            ok "Gemini key saved, provider set to gemini"
        fi
        ;;
    3)
        printf "  Groq API key: "
        read -r api_key
        if [ -n "$api_key" ]; then
            sed -i "s/GROQ_API_KEY=.*/GROQ_API_KEY=$api_key/" "$ENV_FILE"
            python3 -c "
import json
with open('$VASHISHTHA_DIR/config.json') as f: c = json.load(f)
c['api']['provider'] = 'groq'
with open('$VASHISHTHA_DIR/config.json', 'w') as f: json.dump(c, f, indent=2)
"
            ok "Groq key saved, provider set to groq"
        fi
        ;;
    *)
        info "Skipping — edit .env manually before running"
        ;;
esac

# ── Done ──────────────────────────────────────────────────────────────────────

printf "\n${GOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
printf "${GREEN}✓ Installation complete${RESET}\n\n"
printf "  Start:  ${GOLD}va run${RESET}\n"
printf "  Query:  ${GOLD}va query${RESET}\n"
printf "  Logs:   ${GOLD}va logs${RESET}\n"
printf "${GOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n\n"
