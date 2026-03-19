"""
tools/__init__.py — Tool Registry
Central registry for all tools.
brain.py gets schemas from here.
loop.py executes tools through here.
Adding a new tool = import it + add to TOOLS and SCHEMAS. That's it.

Device tools (termux-api) are conditionally excluded from schemas
if config.json device.termux_api is false — agent won't see them.
"""

import json
from pathlib import Path

from tools import shell, files, web, device, memory_tool, code_runner, translate

# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS: dict = {
    "shell":              shell.run,
    "read_file":          files.read,
    "write_file":         files.write,
    "list_dir":           files.list_dir,
    "search_files":       files.search,
    "web_search":         web.search,
    "fetch_page":         web.fetch_page,
    "deep_search":        web.deep_search,
    "search_news":        web.search_news,
    "search_wikipedia":   web.search_wikipedia,
    "battery_status":     device.battery_status,
    "get_location":       device.get_location,
    "clipboard_get":      device.clipboard_get,
    "clipboard_set":      device.clipboard_set,
    "send_notification":  device.send_notification,
    "send_sms":           device.send_sms,
    "get_sms":            device.get_sms,
    "take_photo":         device.take_photo,
    "tts_speak":          device.tts_speak,
    "torch":              device.torch,
    "get_contacts":       device.get_contacts,
    "vibrate":            device.vibrate,
    "wifi_info":          device.wifi_info,
    "remember":           memory_tool.remember,
    "recall":             memory_tool.recall,
    "search_memory":      memory_tool.search_memory,
    "list_memory":        memory_tool.list_memory,
    "forget":             memory_tool.forget,
    "execute_code":       code_runner.execute_code,
    "sandbox_status":     code_runner.sandbox_status,
    "list_saved_code":    code_runner.list_saved,
    "translate":          translate.translate,
    "detect_language":    translate.detect_language,
}

# ── Device tool names — excluded from schemas if termux_api=false ──────────────

_DEVICE_TOOL_NAMES = {
    "battery_status", "get_location", "clipboard_get", "clipboard_set",
    "send_notification", "send_sms", "get_sms", "take_photo",
    "tts_speak", "torch", "get_contacts", "vibrate", "wifi_info",
}

# ── Tool schemas ──────────────────────────────────────────────────────────────

_ALL_SCHEMAS: list[dict] = [
    {
        "name": "shell",
        "description": (
            "Run a terminal command in Termux. Returns stdout + stderr. "
            "Use for system operations, running scripts, checking files, git, etc. "
            "Destructive commands (rm, delete, reboot etc.) will require user confirmation."
        ),
        "parameters": {
            "command": {"type": "string", "description": "The shell command to execute."}
        },
        "required": ["command"],
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file. Returns the file content as text.",
        "parameters": {
            "path": {"type": "string", "description": "Absolute or relative path to the file."}
        },
        "required": ["path"],
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist. Overwrites if it does.",
        "parameters": {
            "path": {"type": "string", "description": "Absolute or relative path to the file."},
            "content": {"type": "string", "description": "Content to write to the file."},
        },
        "required": ["path", "content"],
    },
    {
        "name": "list_dir",
        "description": "List files and directories at a given path.",
        "parameters": {
            "path": {"type": "string", "description": "Directory path to list."}
        },
        "required": ["path"],
    },
    {
        "name": "search_files",
        "description": "Search for files matching a pattern or containing specific text.",
        "parameters": {
            "path": {"type": "string", "description": "Directory to search in."},
            "query": {"type": "string", "description": "Filename pattern or text to search for."},
        },
        "required": ["path", "query"],
    },
    {
        "name": "web_search",
        "description": "Search the web and return a list of results with titles, URLs, and snippets.",
        "parameters": {
            "query": {"type": "string", "description": "Search query."}
        },
        "required": ["query"],
    },
    {
        "name": "fetch_page",
        "description": "Fetch the text content of a web page at a given URL.",
        "parameters": {
            "url": {"type": "string", "description": "Full URL of the page to fetch."}
        },
        "required": ["url"],
    },
    {
        "name": "deep_search",
        "description": (
            "Perplexity-style deep research: search + fetch multiple sources + synthesize cited answer. "
            "Use when user wants a thorough researched answer, not just links. "
            "Slower than web_search but much more comprehensive. "
            "Best for: factual questions, how-to, current events, comparisons, research tasks."
        ),
        "parameters": {
            "query": {"type": "string", "description": "Research query — be specific."},
            "max_sources": {"type": "integer", "description": "Number of sources to fetch. Default 4. Max 6."},
        },
        "required": ["query"],
    },
    {
        "name": "search_news",
        "description": "Search for recent news on a topic. Use when user asks about current events, latest updates, or recent developments.",
        "parameters": {
            "query": {"type": "string", "description": "News search query."}
        },
        "required": ["query"],
    },
    {
        "name": "search_wikipedia",
        "description": "Search Wikipedia for factual information. Fast and structured. Use for definitions, historical facts, people, places, concepts.",
        "parameters": {
            "query": {"type": "string", "description": "Wikipedia search query."}
        },
        "required": ["query"],
    },
    {
        "name": "battery_status",
        "description": "Get device battery level and charging status.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "get_location",
        "description": "Get current GPS location. Returns latitude, longitude, altitude, accuracy.",
        "parameters": {
            "provider": {"type": "string", "description": "gps (accurate, slow) or network (fast, less accurate). Default: gps"}
        },
        "required": [],
    },
    {
        "name": "clipboard_get",
        "description": "Get current clipboard contents.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "clipboard_set",
        "description": "Set clipboard contents.",
        "parameters": {
            "text": {"type": "string", "description": "Text to set in clipboard."}
        },
        "required": ["text"],
    },
    {
        "name": "send_notification",
        "description": "Push a notification to the Android status bar.",
        "parameters": {
            "title": {"type": "string", "description": "Notification title."},
            "content": {"type": "string", "description": "Notification body text."},
        },
        "required": ["title", "content"],
    },
    {
        "name": "send_sms",
        "description": "Send an SMS message. ALWAYS requires user confirmation before sending.",
        "parameters": {
            "number": {"type": "string", "description": "Phone number to send to."},
            "message": {"type": "string", "description": "SMS message content."},
        },
        "required": ["number", "message"],
    },
    {
        "name": "get_sms",
        "description": "Read SMS messages from inbox or sent box.",
        "parameters": {
            "limit": {"type": "integer", "description": "Number of messages to retrieve. Default: 10."},
            "box": {"type": "string", "description": "inbox, sent, draft, all. Default: inbox."},
        },
        "required": [],
    },
    {
        "name": "take_photo",
        "description": "Take a photo using the device camera.",
        "parameters": {
            "camera": {"type": "integer", "description": "0 = back camera, 1 = front camera. Default: 0."},
            "output_path": {"type": "string", "description": "Path to save photo. Optional."},
        },
        "required": [],
    },
    {
        "name": "tts_speak",
        "description": "Speak text aloud using Android TTS.",
        "parameters": {
            "text": {"type": "string", "description": "Text to speak."},
        },
        "required": ["text"],
    },
    {
        "name": "torch",
        "description": "Toggle device flashlight on or off.",
        "parameters": {
            "state": {"type": "string", "description": "on or off."},
        },
        "required": ["state"],
    },
    {
        "name": "get_contacts",
        "description": "Get device contacts list.",
        "parameters": {
            "limit": {"type": "integer", "description": "Max contacts to return. Default: 20."},
        },
        "required": [],
    },
    {
        "name": "vibrate",
        "description": "Vibrate the device.",
        "parameters": {
            "duration_ms": {"type": "integer", "description": "Vibration duration in milliseconds. Default: 300."},
        },
        "required": [],
    },
    {
        "name": "wifi_info",
        "description": "Get current WiFi connection info — SSID, IP, signal strength.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "remember",
        "description": (
            "Store something in long-term memory. Use proactively when user shares "
            "their name, preferences, decisions, project details, or anything worth remembering across sessions. "
            "Use descriptive snake_case keys. e.g. user_name, pref_language, fact_github_username."
        ),
        "parameters": {
            "key": {"type": "string", "description": "Unique snake_case identifier."},
            "value": {
                "type": "string",
                "description": (
                    "What to remember. Infer correct type — int, float, bool, list, dict, str. "
                    "Never stringify unnecessarily."
                )
            },
            "category": {"type": "string", "description": "user | fact | preference | project | context. Default: fact"},
            "importance": {"type": "integer", "description": "1=normal, 2=important, 3=critical. Default: 1"},
        },
        "required": ["key", "value"],
    },
    {
        "name": "recall",
        "description": "Retrieve a specific memory entry by its exact key.",
        "parameters": {
            "key": {"type": "string", "description": "The exact key to retrieve."}
        },
        "required": ["key"],
    },
    {
        "name": "search_memory",
        "description": "Search long-term memory by keyword. Searches both keys and values. Use before answering personal questions.",
        "parameters": {
            "query": {"type": "string", "description": "Search term."}
        },
        "required": ["query"],
    },
    {
        "name": "list_memory",
        "description": "List all long-term memory entries, optionally filtered by category.",
        "parameters": {
            "category": {"type": "string", "description": "user | fact | preference | project | context. Leave empty for all."}
        },
        "required": [],
    },
    {
        "name": "forget",
        "description": "Remove an entry from long-term memory by key.",
        "parameters": {
            "key": {"type": "string", "description": "The exact key to remove."}
        },
        "required": ["key"],
    },
    {
        "name": "execute_code",
        "description": (
            "Execute code in an isolated proot sandbox. "
            "ALWAYS use this for running code — NEVER use write_file + shell for code execution. "
            "Code runs with empty environment — no API keys or host paths visible. "
            "Always requires user confirmation before running. "
            "Supported languages: python, javascript/node, java (if installed). "
            "Call sandbox_status first if unsure what languages are available."
        ),
        "parameters": {
            "language": {"type": "string", "description": "Language: python, javascript, node, java."},
            "code": {"type": "string", "description": "Complete, self-contained source code. No stdin — do not use input()."},
            "save_as": {"type": "string", "description": "Optional filename to persist in sandbox/saved/. Omit to auto-delete after run."},
        },
        "required": ["language", "code"],
    },
    {
        "name": "sandbox_status",
        "description": "Check sandbox state — available languages, linked binaries, isolation mode. Use before execute_code if unsure.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "list_saved_code",
        "description": "List code files saved in sandbox/saved/.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "translate",
        "description": (
            "Translate text to a target language. "
            "LLM-based — accurate for all major languages. "
            "Checks user's translation_preferences from memory first. "
            "Use for: translating user content, multilingual tasks, language conversion."
        ),
        "parameters": {
            "text": {"type": "string", "description": "Text to translate."},
            "to_lang": {"type": "string", "description": "Target language — name or ISO code. e.g. 'hindi', 'hi', 'french', 'fr'. Leave empty to use user preference (default: hi)."},
            "from_lang": {"type": "string", "description": "Source language. Default: auto-detect."},
        },
        "required": ["text"],
    },
    {
        "name": "detect_language",
        "description": "Detect the language of a given text. Returns language name and ISO code.",
        "parameters": {
            "text": {"type": "string", "description": "Text to detect language of."}
        },
        "required": ["text"],
    },
]


# ── Public interface ──────────────────────────────────────────────────────────

def execute(tool_name: str, args: dict) -> str:
    """Execute a tool by name with given args. Returns result as string."""
    if tool_name not in TOOLS:
        return f"Error: tool '{tool_name}' not found. Available: {list(TOOLS.keys())}"
    try:
        return str(TOOLS[tool_name](**args))
    except TypeError as e:
        return f"Error: wrong arguments for '{tool_name}': {e}"
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"


def get_schemas() -> list[dict]:
    """
    Return tool schemas for brain.py to send to the LLM.
    Device tools excluded if config.json device.termux_api is false.
    """
    termux_api = True
    try:
        cfg_path = Path(__file__).parent.parent / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            termux_api = cfg.get("device", {}).get("termux_api", True)
    except Exception:
        pass

    if termux_api:
        return _ALL_SCHEMAS

    return [s for s in _ALL_SCHEMAS if s["name"] not in _DEVICE_TOOL_NAMES]
