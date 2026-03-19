"""
memory.py — Short-term and long-term memory
Short-term: per-session conversation history, RAM + disk.
Long-term: structured persistent store — user info, facts, preferences, projects.
           Flexible schema — any key-value data, searchable, categorized.
"""

import json
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "memory_store" / "sessions"
LONG_TERM_PATH = BASE_DIR / "memory_store" / "long_term.json"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str                          # "user" | "assistant" | "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_name: str | None = None


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class MemoryEntry:
    """A single long-term memory entry."""
    key: str                           # unique identifier
    value: Any                         # the stored value
    category: str                      # "user" | "fact" | "preference" | "project" | "context"
    source: str                        # "agent" | "user" | "system"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    importance: int = 1                # 1-3, higher = more important, shown first


# ── Memory class ──────────────────────────────────────────────────────────────

class Memory:
    """
    Two-tier memory system.

    Short-term: per-session conversation history.
      - Stored in RAM + persisted to disk on each write
      - Last N messages sent to LLM (configurable window)
      - Sessions survive process restarts

    Long-term: flexible persistent store.
      - Structured entries with category, importance, source
      - Searchable by key or category
      - Injected as context into every system prompt
      - Agent can read/write via memory_tool.py
    """

    def __init__(self, memory_window: int = 20):
        self.memory_window = memory_window
        self._sessions: dict[str, Session] = {}
        self._entries: dict[str, MemoryEntry] = {}   # key → MemoryEntry
        self._load_long_term()

    # ── Session management ────────────────────────────────────────────────────

    def new_session(self) -> str:
        session_id = str(uuid.uuid4())[:8]
        self._sessions[session_id] = Session(session_id=session_id)
        print(f"[memory] New session: {session_id}")
        return session_id

    def load_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            return True

        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text())
            messages = [Message(**m) for m in data.get("messages", [])]
            self._sessions[session_id] = Session(
                session_id=session_id,
                messages=messages,
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
            )
            print(f"[memory] Loaded session: {session_id} ({len(messages)} messages)")
            return True
        except Exception as e:
            print(f"[memory] Failed to load session {session_id}: {e}")
            return False

    # ── Message operations ────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
    ):
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)

        msg = Message(role=role, content=content, tool_name=tool_name)
        session = self._sessions[session_id]
        session.messages.append(msg)
        session.updated_at = time.time()
        self._save_session(session_id)

    def get_history(self, session_id: str) -> list[dict]:
        if session_id not in self._sessions:
            return []

        messages = self._sessions[session_id].messages
        windowed = messages[-self.memory_window:]

        result = []
        for msg in windowed:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_name:
                entry["tool_name"] = msg.tool_name
            result.append(entry)

        return result

    def get_session_text(self, session_id: str) -> str:
        """Plain text of session — used for auto-extraction."""
        if session_id not in self._sessions:
            return ""

        messages = self._sessions[session_id].messages
        lines = []
        for msg in messages:
            prefix = {
                "user": "User",
                "assistant": "Vashishtha",
                "tool": f"Tool({msg.tool_name})",
            }.get(msg.role, msg.role)
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            print(f"[memory] Cleared session from RAM: {session_id}")

    # ── Long-term memory — write ──────────────────────────────────────────────

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "fact",
        source: str = "agent",
        importance: int = 1,
    ) -> str:
        """
        Store or update a long-term memory entry.
        If key exists, updates value and timestamp.

        Categories: user | fact | preference | project | context
        Importance: 1 (normal) | 2 (important) | 3 (critical)
        """
        # Defensive cast — LLMs sometimes pass importance as string
        try:
            importance = int(importance)
        except (TypeError, ValueError):
            importance = 1
        importance = max(1, min(3, importance))  # clamp to 1-3

        if key in self._entries:
            entry = self._entries[key]
            entry.value = value
            entry.updated_at = time.time()
            entry.importance = max(entry.importance, importance)
            print(f"[memory] Updated: {key}")
        else:
            self._entries[key] = MemoryEntry(
                key=key,
                value=value,
                category=category,
                source=source,
                importance=importance,
            )
            print(f"[memory] Remembered: {key}")

        self._save_long_term()
        return f"Remembered: {key} = {value}"

    def forget(self, key: str) -> str:
        """Remove a long-term memory entry."""
        if key in self._entries:
            del self._entries[key]
            self._save_long_term()
            print(f"[memory] Forgot: {key}")
            return f"Forgotten: {key}"
        return f"Not found in memory: {key}"

    # ── Long-term memory — read ───────────────────────────────────────────────

    def recall(self, key: str) -> Any | None:
        """Retrieve a specific memory entry by key."""
        entry = self._entries.get(key)
        return entry.value if entry else None

    def search(self, query: str) -> list[dict]:
        """
        Search memory entries by key or value (case-insensitive substring match).
        Returns list of matching entries sorted by importance.
        """
        query_lower = query.lower()
        results = []

        for entry in self._entries.values():
            key_match = query_lower in entry.key.lower()
            val_str = str(entry.value).lower()
            val_match = query_lower in val_str

            if key_match or val_match:
                results.append({
                    "key": entry.key,
                    "value": entry.value,
                    "category": entry.category,
                    "importance": entry.importance,
                })

        results.sort(key=lambda x: x["importance"], reverse=True)
        return results

    def list_by_category(self, category: str) -> list[dict]:
        """List all entries in a category."""
        return [
            {"key": e.key, "value": e.value, "importance": e.importance}
            for e in self._entries.values()
            if e.category == category
        ]

    def get_all(self) -> dict[str, Any]:
        """Return full long-term memory as dict."""
        return {k: asdict(v) for k, v in self._entries.items()}

    def get_long_term_summary(self) -> str:
        """
        Concise summary for system prompt injection.
        Shows important entries first, grouped by category.
        Stays short — not a dump, just context.
        """
        if not self._entries:
            return ""

        # Sort by importance desc, then by category
        entries = sorted(
            self._entries.values(),
            key=lambda e: (-e.importance, e.category)
        )

        lines = []
        seen_categories = set()

        for entry in entries:
            cat = entry.category
            if cat not in seen_categories:
                seen_categories.add(cat)

            val = entry.value
            if isinstance(val, dict):
                val = json.dumps(val, ensure_ascii=False)
            elif isinstance(val, list):
                val = ", ".join(str(v) for v in val[:5])

            # Skip empty string values — template fields not yet filled
            if val == "" or val == "null" or val is None:
                continue

            lines.append(f"- [{cat}] {entry.key}: {val}")

            # Cap at 20 entries — don't flood the system prompt
            if len(lines) >= 20:
                remaining = len(self._entries) - 20
                if remaining > 0:
                    lines.append(f"- ... ({remaining} more entries)")
                break

        if not lines:
            return ""

        return "## Long-term memory\n" + "\n".join(lines)

    # ── Legacy compatibility ──────────────────────────────────────────────────
    # Keep these so existing code doesn't break

    def get_long_term(self) -> dict:
        """Return full memory as dict. Legacy endpoint."""
        return self.get_all()

    def update_long_term(self, key: str, value: Any):
        """Legacy method — maps to remember()."""
        self.remember(key, value, category="context", source="system")

    def add_fact(self, fact: str):
        """Legacy method — store fact with auto-generated key."""
        key = f"fact_{int(time.time())}"
        self.remember(key, fact, category="fact", source="agent")

    def forget_fact(self, fact: str):
        """Legacy method — search and remove matching fact."""
        for key, entry in list(self._entries.items()):
            if entry.category == "fact" and str(entry.value) == fact:
                self.forget(key)
                return

    # ── Private helpers ───────────────────────────────────────────────────────

    def _save_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if not session:
            return
        try:
            path = SESSIONS_DIR / f"{session_id}.json"
            data = {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "messages": [asdict(m) for m in session.messages],
            }
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[memory] Failed to save session {session_id}: {e}")

    def _save_long_term(self):
        try:
            data = {k: asdict(v) for k, v in self._entries.items()}
            LONG_TERM_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            print(f"[memory] Failed to save long-term: {e}")

    def _load_long_term(self):
        if not LONG_TERM_PATH.exists():
            self._migrate_legacy()
            return

        try:
            data = json.loads(LONG_TERM_PATH.read_text())

            # Detect legacy format (flat dict with user/projects/facts keys)
            if "user" in data or "facts" in data or "projects" in data:
                self._migrate_legacy(data)
                return

            # New format — load MemoryEntry objects
            for key, entry_data in data.items():
                try:
                    # Defensive cast — importance may be string from LLM
                    if "importance" in entry_data:
                        try:
                            entry_data["importance"] = int(entry_data["importance"])
                        except (TypeError, ValueError):
                            entry_data["importance"] = 1
                    self._entries[key] = MemoryEntry(**entry_data)
                except Exception:
                    pass

            print(f"[memory] Loaded {len(self._entries)} long-term entries")

        except Exception as e:
            print(f"[memory] Failed to load long-term: {e}")
            self._migrate_legacy()

    def _migrate_legacy(self, data: dict | None = None):
        """Initialize fresh memory or convert old long_term.json format."""
        if data is None:
            # Fresh start — seed with empty template fields.
            # Agent will fill these in through conversation.
            # No personal data — this is the production/clone-ready template.
            self.remember(
                "device", "",
                category="context", source="system", importance=2
            )
            self.remember(
                "translation_preferences",
                {
                    "default_from": "auto",
                    "default_to": "hi",
                    "frequent_pairs": [],
                    "preferred_model_loaded": None,
                },
                category="preference", source="system", importance=1
            )
            print("[memory] Initialized fresh long-term memory")
            return

        # ── Migrate from old format ───────────────────────────────────────────
        user = data.get("user", {})
        if user.get("name"):
            self.remember("user_name", user["name"], category="user", source="system", importance=3)
        if user.get("preferences"):
            for k, v in user["preferences"].items():
                self.remember(f"pref_{k}", v, category="preference", source="system")
        if user.get("devices", {}).get("main"):
            self.remember("device", user["devices"]["main"], category="context", source="system", importance=2)

        # Migrate facts
        for i, fact in enumerate(data.get("facts", [])):
            self.remember(f"fact_{i}", fact, category="fact", source="system")

        # Migrate translation prefs
        trans = data.get("translation_preferences", {})
        if trans:
            self.remember("translation_preferences", trans, category="preference", source="system")

        # Note: projects deliberately NOT migrated — personal data

        print(f"[memory] Migrated legacy memory — {len(self._entries)} entries")
        self._save_long_term()
