# Device Skill — Vashishtha

## Device
Rooted Android, Termux
Root available via `su -c "command"` — always confirm before use.

## Availability
Device tools require `termux-api` package and are auto-detected at startup.
If `termux_api=false` in config.json, ALL device tools below are unavailable —
they will not appear in your tool list. Use `shell` to check:
```bash
pkg list-installed | grep termux-api
```
To install: `pkg install termux-api`

## Termux Storage Paths
Prefer these symlinks over hardcoded /storage/emulated/0/ paths:
- `~/storage/shared/` → internal storage root
- `~/storage/downloads/` → Downloads folder
- `~/storage/dcim/` → DCIM / camera photos
- `~/storage/pictures/` → Pictures
- `~/storage/music/` → Music
- `~/storage/movies/` → Movies

If symlinks missing: run `termux-setup-storage`

## Available Agent Tools (device.py)
These are registered tools — use them directly, don't shell termux-api manually:

| Tool | What it does |
|---|---|
| `battery_status` | Battery level, status, plugged state |
| `get_location` | GPS coordinates (provider: gps or network) |
| `clipboard_get` | Read clipboard |
| `clipboard_set` | Write to clipboard |
| `send_notification` | Push notification to status bar |
| `send_sms` | Send SMS — ALWAYS requires confirmation |
| `get_sms` | Read SMS inbox/sent |
| `take_photo` | Camera photo (0=back, 1=front) |
| `tts_speak` | Speak text via Android TTS |
| `torch` | Flashlight on/off |
| `get_contacts` | Device contacts list |
| `vibrate` | Vibrate device |
| `wifi_info` | WiFi SSID, IP, signal strength |

## Raw termux-api (use shell tool only if agent tool unavailable)
- `termux-microphone-record` — audio recording (no agent tool yet)
- `termux-sensor` — sensor data
- `termux-telephony-deviceinfo` — IMEI, network info

## Root Rules
- ANY `su` or `su -c` command = always confirm, no exceptions
- If `root_available=false` in config.json, su commands are blocked entirely
- Log intent before running: what will this do?
- Never chain multiple destructive root commands without separate confirmations

## Cautions
- SMS sends real messages — always confirm number AND content
- Camera — confirm before use
- Location — confirm before sharing
- Root — confirm always, no exceptions
