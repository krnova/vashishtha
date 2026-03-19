"""
tools/shell.py — Shell Tool
Execute terminal commands in Termux.
Root commands via `su -c` when needed.
All output captured and returned as string.
"""

import shutil
import subprocess
from pathlib import Path


DEFAULT_TIMEOUT = 30       # seconds
ROOT_TIMEOUT = 15          # shorter timeout for root commands — fail fast


def run(command: str, cwd: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Execute a shell command. Returns combined stdout + stderr as string.

    Args:
        command: Shell command string to execute.
        cwd:     Working directory. Defaults to home directory.
        timeout: Max seconds to wait. Kills process if exceeded.

    Returns:
        String with stdout + stderr, or error message.
    """
    if not command or not command.strip():
        return "Error: empty command"

    working_dir = cwd or str(Path.home())

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )

        output_parts = []

        if result.stdout.strip():
            output_parts.append(result.stdout.strip())

        if result.stderr.strip():
            output_parts.append(f"[stderr]: {result.stderr.strip()}")

        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        if not output_parts:
            return f"[Command completed with exit code {result.returncode}]"

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s — '{command}'"

    except FileNotFoundError as e:
        return f"Error: command not found — {e}"

    except Exception as e:
        return f"Error: {str(e)}"


def run_root(command: str, cwd: str | None = None) -> str:
    """
    Execute a command with root via `su -c`.
    Only called after explicit user confirmation via loop.py.

    Args:
        command: Command to run as root.
        cwd:     Working directory.

    Returns:
        Combined stdout + stderr as string.
    """
    root_command = f'su -c "{command}"'
    return run(root_command, cwd=cwd, timeout=ROOT_TIMEOUT)


def which(binary: str) -> str | None:
    """Check if a binary exists in PATH. Returns path or None."""
    return shutil.which(binary)


def get_env() -> dict[str, str]:
    """Return current environment variables as dict. Useful for debugging."""
    import os
    return dict(os.environ)
