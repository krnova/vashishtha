"""
tools/device.py — Device Control Tool
termux-api bridge for hardware access.
Requires: pkg install termux-api
All commands run via shell — termux-api package must be installed.
"""

import subprocess
import json
from pathlib import Path


TERMUX_API_TIMEOUT = 10    # seconds — termux-api can be slow sometimes


def _run(command: str) -> tuple[str, str, int]:
    """Run a termux-api command. Returns (stdout, stderr, returncode)."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=TERMUX_API_TIMEOUT,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def _parse_json(output: str) -> dict | list | None:
    """Parse JSON output from termux-api commands."""
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


# ── Battery ───────────────────────────────────────────────────────────────────

def battery_status() -> str:
    """Get battery level and charging status."""
    stdout, stderr, code = _run("termux-battery-status")
    if code != 0 or not stdout:
        return f"Error: battery status failed — {stderr or 'no output'}"

    data = _parse_json(stdout)
    if not data:
        return stdout

    level = data.get("percentage", "?")
    status = data.get("status", "?")
    plugged = data.get("plugged", "?")
    return f"Battery: {level}% | Status: {status} | Plugged: {plugged}"


# ── Location ──────────────────────────────────────────────────────────────────

def get_location(provider: str = "gps") -> str:
    """
    Get current GPS location.
    provider: "gps" (accurate, slow) or "network" (fast, less accurate)
    """
    stdout, stderr, code = _run(f"termux-location -p {provider} -r once")
    if code != 0 or not stdout:
        return f"Error: location failed — {stderr or 'no output'}"

    data = _parse_json(stdout)
    if not data:
        return stdout

    lat = data.get("latitude", "?")
    lon = data.get("longitude", "?")
    alt = data.get("altitude", "?")
    acc = data.get("accuracy", "?")
    return f"Location: {lat}, {lon} | Altitude: {alt}m | Accuracy: {acc}m"


# ── Clipboard ─────────────────────────────────────────────────────────────────

def clipboard_get() -> str:
    """Get current clipboard contents."""
    stdout, stderr, code = _run("termux-clipboard-get")
    if code != 0:
        return f"Error: clipboard read failed — {stderr or 'unknown'}"
    return stdout if stdout else "(clipboard is empty)"


def clipboard_set(text: str) -> str:
    """Set clipboard contents."""
    escaped = text.replace("'", "'\\''")
    _, stderr, code = _run(f"termux-clipboard-set '{escaped}'")
    if code != 0:
        return f"Error: clipboard write failed — {stderr or 'unknown'}"
    return f"Clipboard set: {text[:80]}{'...' if len(text) > 80 else ''}"


# ── Notifications ─────────────────────────────────────────────────────────────

def send_notification(title: str, content: str, notification_id: int = 1) -> str:
    """Push a notification to the Android status bar."""
    escaped_title = title.replace('"', '\\"')
    escaped_content = content.replace('"', '\\"')
    _, stderr, code = _run(
        f'termux-notification --title "{escaped_title}" '
        f'--content "{escaped_content}" '
        f'--id {notification_id}'
    )
    if code != 0:
        return f"Error: notification failed — {stderr or 'unknown'}"
    return f"Notification sent: {title}"


def remove_notification(notification_id: int = 1) -> str:
    """Remove a notification by ID."""
    _, stderr, code = _run(f"termux-notification-remove {notification_id}")
    if code != 0:
        return f"Error: remove notification failed — {stderr or 'unknown'}"
    return f"Notification {notification_id} removed"


# ── SMS ───────────────────────────────────────────────────────────────────────

def send_sms(number: str, message: str) -> str:
    """
    Send an SMS message.
    NOTE: This function is registered but ALWAYS requires confirmation in loop.py.
    Real SMS — confirm number and content before calling.
    """
    escaped_msg = message.replace('"', '\\"')
    _, stderr, code = _run(f'termux-sms-send -n "{number}" "{escaped_msg}"')
    if code != 0:
        return f"Error: SMS failed — {stderr or 'unknown'}"
    return f"SMS sent to {number}"


def get_sms(limit: int = 10, box: str = "inbox") -> str:
    """
    Read SMS messages.
    box: "inbox" | "sent" | "draft" | "outbox" | "failed" | "queued" | "all"
    """
    stdout, stderr, code = _run(f"termux-sms-list -l {limit} -t {box}")
    if code != 0 or not stdout:
        return f"Error: read SMS failed — {stderr or 'no output'}"

    data = _parse_json(stdout)
    if not data:
        return f"No messages in {box}"

    lines = [f"SMS {box} (last {len(data)}):"]
    for msg in data:
        sender = msg.get("address", "unknown")
        body = msg.get("body", "")[:100]
        date = msg.get("received", "")[:10]
        lines.append(f"\n[{date}] From: {sender}\n{body}")

    return "\n".join(lines)


# ── Camera ────────────────────────────────────────────────────────────────────

def take_photo(camera: int = 0, output_path: str | None = None) -> str:
    """
    Take a photo.
    camera: 0 = back, 1 = front
    output_path: where to save. Defaults to ~/vashishtha_photo.jpg
    """
    path = output_path or str(Path.home() / "vashishtha_photo.jpg")
    _, stderr, code = _run(f"termux-camera-photo -c {camera} {path}")
    if code != 0:
        return f"Error: camera failed — {stderr or 'unknown'}"
    return f"Photo saved: {path}"


# ── TTS ───────────────────────────────────────────────────────────────────────

def tts_speak(text: str, rate: float = 1.0) -> str:
    """
    Speak text using Android TTS via termux-api.
    Fallback TTS — used when espeak/pyttsx3 not available.
    """
    escaped = text.replace('"', '\\"')
    _, stderr, code = _run(f'termux-tts-speak -r {rate} "{escaped}"')
    if code != 0:
        return f"Error: TTS failed — {stderr or 'unknown'}"
    return f"Spoken: {text[:80]}"


# ── Torch / Flashlight ────────────────────────────────────────────────────────

def torch(state: str = "on") -> str:
    """Toggle flashlight. state: 'on' or 'off'"""
    if state not in ("on", "off"):
        return "Error: state must be 'on' or 'off'"
    _, stderr, code = _run(f"termux-torch {state}")
    if code != 0:
        return f"Error: torch failed — {stderr or 'unknown'}"
    return f"Torch: {state}"


# ── Contacts ──────────────────────────────────────────────────────────────────

def get_contacts(limit: int = 20) -> str:
    """Get device contacts list."""
    stdout, stderr, code = _run("termux-contact-list")
    if code != 0 or not stdout:
        return f"Error: contacts failed — {stderr or 'no output'}"

    data = _parse_json(stdout)
    if not data:
        return stdout

    lines = [f"Contacts ({len(data)} total, showing {min(limit, len(data))}):"]
    for contact in data[:limit]:
        name = contact.get("name", "?")
        number = contact.get("number", "?")
        lines.append(f"  {name} — {number}")

    return "\n".join(lines)


# ── Vibrate ───────────────────────────────────────────────────────────────────

def vibrate(duration_ms: int = 300) -> str:
    """Vibrate the device."""
    _, stderr, code = _run(f"termux-vibrate -d {duration_ms}")
    if code != 0:
        return f"Error: vibrate failed — {stderr or 'unknown'}"
    return f"Vibrated for {duration_ms}ms"


# ── WiFi info ─────────────────────────────────────────────────────────────────

def wifi_info() -> str:
    """Get current WiFi connection info."""
    stdout, stderr, code = _run("termux-wifi-connectioninfo")
    if code != 0 or not stdout:
        return f"Error: wifi info failed — {stderr or 'no output'}"

    data = _parse_json(stdout)
    if not data:
        return stdout

    ssid = data.get("ssid", "?")
    ip = data.get("ip", "?")
    rssi = data.get("rssi", "?")
    return f"WiFi: {ssid} | IP: {ip} | Signal: {rssi}dBm"
