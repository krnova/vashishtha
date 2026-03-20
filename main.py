"""
main.py — Entry Point
Starts Vashishtha. Detects root/termux-api capabilities at startup
and writes them to config.json before the agent initializes.
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).parent / "config.json"


def check_env(config: dict):
    """Check that the right API key is set for the configured provider."""
    provider = config.get("api", {}).get("provider", "gemini")

    if provider == "nim":
        if not os.getenv("NIM_API_KEY"):
            print("✗ NIM_API_KEY not set. Add it to your .env file.")
            print("  (config.json provider is set to 'nim')")
            sys.exit(1)
    else:
        if not os.getenv("GEMINI_API_KEY"):
            print("✗ GEMINI_API_KEY not set. Add it to your .env file.")
            sys.exit(1)


def detect_capabilities(config: dict) -> dict:
    """
    Auto-detect root and termux-api availability.
    Writes results to config.json device section.

    root_available  — tests `su -c id`, checks uid=0 in output
    termux_api      — checks if termux-battery-status binary exists in PATH
    root_confirm_always — never touched, always user's decision
    """
    device_cfg = config.get("device", {})

    # ── Root detection ────────────────────────────────────────────────────────
    root_available = False
    try:
        result = subprocess.run(
            ["su", "-c", "id"],
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
        root_available = result.returncode == 0 and "uid=0" in result.stdout
    except Exception:
        root_available = False

    # ── termux-api detection ──────────────────────────────────────────────────
    termux_api = shutil.which("termux-battery-status") is not None

    # ── Update device section — never touch root_confirm_always ───────────────
    device_cfg["root_available"] = root_available
    device_cfg["termux_api"] = termux_api
    config["device"] = device_cfg

    # ── Persist to config.json ────────────────────────────────────────────────
    try:
        CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[main] ⚠ Could not write config.json: {e}")

    # ── Report ────────────────────────────────────────────────────────────────
    root_str  = "✓ root"    if root_available else "✗ no root"
    api_str   = "✓ termux-api" if termux_api   else "✗ no termux-api"
    print(f"[main] Device: {root_str} | {api_str}")

    return config


def main():
    print("┌─────────────────────────────────┐")
    print("│  वशिष्ठ — Vashishtha             │")
    print("│  Sovereign Agent                │")
    print("└─────────────────────────────────┘\n")

    # Load config
    config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    # Check API keys before anything else
    check_env(config)

    # Auto-detect capabilities, update config.json
    config = detect_capabilities(config)

    # Start Flask API — Brain() will reload config and pick up detected values
    from api import start

    port = config.get("interfaces", {}).get("api_port", 5000)
    debug = os.getenv("FLASK_DEBUG", "0") == "1"

    start(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    main()
