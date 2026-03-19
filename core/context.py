"""
context.py — Session State Management
Tracks everything about the current active session.
One Context instance per session, lives inside the Loop.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent


@dataclass
class Context:
    """
    Holds the current session's state.
    Passed into Loop and Brain so everything shares the same context.
    """

    session_id: str

    # Working directory for file/shell operations
    cwd: str = field(default_factory=lambda: str(Path.home()))

    # Active project — agent scopes file ops to this when set
    active_project: str | None = None
    active_project_path: str | None = None

    # Pending confirmation — stored here between user turns
    pending_action: dict | None = None

    # Session start time
    started_at: float = field(default_factory=time.time)

    def set_project(self, name: str, path: str | None = None):
        """Switch active project context."""
        self.active_project = name
        if path:
            self.active_project_path = path
            self.cwd = path
        print(f"[context] Active project: {name} @ {self.active_project_path or 'no path'}")

    def clear_project(self):
        """Clear active project, reset cwd to home."""
        self.active_project = None
        self.active_project_path = None
        self.cwd = str(Path.home())
        print("[context] Project context cleared")

    def set_pending(self, action: dict):
        """Store a pending action waiting for user confirmation."""
        self.pending_action = action

    def clear_pending(self):
        """Clear pending action after it's been confirmed or cancelled."""
        self.pending_action = None

    def has_pending(self) -> bool:
        return self.pending_action is not None

    def summary(self) -> str:
        """Human-readable summary of current context. Used in debug/logs."""
        lines = [
            f"Session: {self.session_id}",
            f"CWD: {self.cwd}",
        ]
        if self.active_project:
            lines.append(f"Project: {self.active_project}")
        if self.pending_action:
            lines.append(f"Pending: {self.pending_action['tool']}({self.pending_action['args']})")
        return " | ".join(lines)
