#!/bin/bash
# install.sh — Vashishtha Installer

set -e

VASHISHTHA_DIR="$(cd "$(dirname "$0")" && pwd)"
WHEEL_BASE="https://github.com/krnova/android-wheels/releases/download"

# ── Colors ────────────────────────────────────────────────────────────────────
GOLD='\033[38;5;220m'
DIM='\033[2m'
BOLD='\033[1m'
GREEN='\033[38;5;82m'
RED='\033[38;5;196m'
ORANGE='\033[38;5;208m'
BLUE='\033[38;5;75m'
RESET='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────
ok()   { printf "  ${GREEN}✓${RESET}  $1\n"; }
skip() { printf "  ${DIM}↷  $1${RESET}\n"; }
fail() { printf "  ${RED}✗  $1${RESET}\n"; }
info() { printf "  ${DIM}   $1${RESET}\n"; }
step() { printf "\n  ${BOLD}${GOLD}$1${RESET}\n\n"; }

pkg_installed() { pkg list-installed 2>/dev/null | grep -q "^$1/"; }
pip_installed() { pip show "$1" &>/dev/null; }

# ── Header ────────────────────────────────────────────────────────────────────

clear
printf "\n  ${BOLD}${GOLD}वशिष्ठ — Vashishtha${RESET}\n"
printf "  ${DIM}installer${RESET}\n"
printf "\n  ${DIM}────────────────────────────────────────${RESET}\n"

# ── Step 1: Termux packages ───────────────────────────────────────────────────

step "termux packages"

PKG_PACKAGES=(python python-cryptography proot-distro git jq)

pkg update -y -q 2>/dev/null || true

for p in "${PKG_PACKAGES[@]}"; do
  if pkg_installed "$p"; then
    skip "$p"
  else
    info "installing $p..."
    pkg install -y "$p" -q 2>/dev/null && ok "$p" || fail "$p"
  fi
done

# termux-api — optional
printf "\n  ${BLUE}install termux-api?${RESET}  ${DIM}SMS · camera · GPS · clipboard · TTS${RESET}  [y/N] "
read -r install_api
if [[ "$install_api" =~ ^[Yy]$ ]]; then
  if pkg_installed "termux-api"; then
    skip "termux-api"
  else
    pkg install -y termux-api -q 2>/dev/null && ok "termux-api" || fail "termux-api"
  fi
else
  info "skipping termux-api — device tools unavailable"
fi

# ── Step 2: Android ARM64 wheels ──────────────────────────────────────────────

step "android ARM64 wheels"

info "pre-built for Python 3.13 + ARM64 — standard pip wheels won't work here"
printf "\n"

WHEELS=(
  "$WHEEL_BASE/v2.41.5-android/pydantic_core-2.41.5-cp313-cp313-android_arm64_v8a.whl"
  "$WHEEL_BASE/v0.13.0-android/jiter-0.13.0-cp313-cp313-android_arm64_v8a.whl"
)

for wheel in "${WHEELS[@]}"; do
  name=$(basename "$wheel" | cut -d- -f1)
  if pip_installed "$name"; then
    skip "$name"
  else
    info "installing $name..."
    pip install --break-system-packages -q "$wheel" 2>/dev/null && ok "$name" || fail "$name"
  fi
done

# ── Step 3: Python packages ───────────────────────────────────────────────────

step "python packages"

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
  bare=$(echo "$pkg" | sed 's/[>=<].*//')
  if pip_installed "$bare"; then
    skip "$pkg"
  else
    info "installing $pkg..."
    pip install --break-system-packages --prefer-binary -q "$pkg" 2>/dev/null && ok "$pkg" || fail "$pkg"
  fi
done

# ── Step 4: Alpine sandbox ────────────────────────────────────────────────────

step "sandbox — Alpine Linux"

ALPINE_ROOTFS="$PREFIX/var/lib/proot-distro/installed-rootfs/alpine"

if [ -d "$ALPINE_ROOTFS" ]; then
  skip "alpine already installed"
else
  info "installing Alpine (~150MB)..."
  proot-distro install alpine && ok "alpine installed" || { fail "alpine install failed"; exit 1; }
fi

printf "\n"
info "installing languages: python3 · nodejs · openjdk17"
printf "\n"

proot-distro login alpine -- sh -c "
  apk update -q
  for p in python3 nodejs openjdk17; do
    if apk info -e \$p >/dev/null 2>&1; then
      printf '  \033[2m↷  %s\033[0m\n' \$p
    else
      apk add -q \$p && printf '  \033[38;5;82m✓\033[0m  %s\n' \$p || printf '  \033[38;5;196m✗\033[0m  %s\n' \$p
    fi
  done
"

# ── Step 5: va CLI ────────────────────────────────────────────────────────────

step "va CLI"

if [ ! -f "$VASHISHTHA_DIR/va" ]; then
  fail "va not found in $VASHISHTHA_DIR"
elif [ -f "$PREFIX/bin/va" ]; then
  skip "va already in \$PREFIX/bin"
else
  cp "$VASHISHTHA_DIR/va" "$PREFIX/bin/va"
  chmod +x "$PREFIX/bin/va"
  ok "va → \$PREFIX/bin/va"
fi

# Install completions if completion file exists
COMPLETION_FILE="$VASHISHTHA_DIR/va-completion.bash"
BASHRC="$HOME/.bashrc"
if [ -f "$COMPLETION_FILE" ]; then
  if grep -q "va-completion.bash" "$BASHRC" 2>/dev/null; then
    skip "completions already in .bashrc"
  else
    echo "" >> "$BASHRC"
    echo "# va completions" >> "$BASHRC"
    echo "[ -f \"$COMPLETION_FILE\" ] && source \"$COMPLETION_FILE\"" >> "$BASHRC"
    ok "completions → .bashrc"
    info "run: source ~/.bashrc"
  fi
fi

# ── Step 6: Config ────────────────────────────────────────────────────────────

step "config"

if [ -f "$VASHISHTHA_DIR/config.json" ]; then
  skip "config.json exists"
else
  cp "$VASHISHTHA_DIR/config.example.json" "$VASHISHTHA_DIR/config.json"
  ok "config.json created"
fi

if [ -f "$VASHISHTHA_DIR/.env" ]; then
  skip ".env exists"
else
  cp "$VASHISHTHA_DIR/.env.example" "$VASHISHTHA_DIR/.env"
  ok ".env created"
fi

# ── Step 7: API key ───────────────────────────────────────────────────────────

step "api key"

ENV_FILE="$VASHISHTHA_DIR/.env"

printf "  provider?\n\n"
printf "    ${GREEN}1${RESET}  NIM    ${DIM}NVIDIA — default, thinking mode${RESET}\n"
printf "    ${GREEN}2${RESET}  Gemini ${DIM}Google${RESET}\n"
printf "    ${GREEN}3${RESET}  Groq   ${DIM}fast inference${RESET}\n"
printf "    ${DIM}0  skip — edit .env manually${RESET}\n"
printf "\n  choice [1]: "
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
      ok "NIM key saved  ·  provider → nim"
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
      ok "Gemini key saved  ·  provider → gemini"
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
      ok "Groq key saved  ·  provider → groq"
    fi
    ;;
  *)
    info "skipping — edit .env before running"
    ;;
esac

# ── Done ──────────────────────────────────────────────────────────────────────

printf "\n  ${DIM}────────────────────────────────────────${RESET}\n"
printf "  ${GREEN}✓  done${RESET}\n\n"
printf "    ${GREEN}va run${RESET}    start agent\n"
printf "    ${GREEN}va query${RESET}  interactive REPL\n"
printf "    ${GREEN}va logs${RESET}   tail logs\n\n"
