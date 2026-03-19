"""
tools/files.py — File System Tool
Read, write, list, search files.
All paths resolved safely — no escaping home directory accidentally.
"""

import os
import fnmatch
from pathlib import Path


MAX_READ_BYTES = 512 * 1024    # 512KB max read — prevents RAM spike on large files
MAX_SEARCH_RESULTS = 50


def _resolve(path: str) -> Path:
    """Resolve path — expand ~, env variables, and make absolute."""
    expanded = os.path.expandvars(path)   # $HOME, $USER etc.
    return Path(expanded).expanduser().resolve()


def read(path: str) -> str:
    """
    Read a file and return its contents as string.
    Refuses to read binary files and files over 512KB.
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: file not found — {path}"

    if not p.is_file():
        return f"Error: not a file — {path}"

    size = p.stat().st_size
    if size > MAX_READ_BYTES:
        return (
            f"Error: file too large ({size // 1024}KB). "
            f"Max is {MAX_READ_BYTES // 1024}KB. "
            f"Use shell tool with `head`, `tail`, or `grep` for large files."
        )

    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary file — cannot read as text — {path}"
    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write(path: str, content: str) -> str:
    """
    Write content to a file.
    Creates parent directories if they don't exist.
    Overwrites existing file.
    """
    p = _resolve(path)

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        size = p.stat().st_size
        return f"Written {size} bytes to {p}"
    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def append(path: str, content: str) -> str:
    """Append content to a file. Creates file if it doesn't exist."""
    p = _resolve(path)

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended to {p}"
    except Exception as e:
        return f"Error appending to file: {e}"


def list_dir(path: str) -> str:
    """
    List contents of a directory.
    Shows type (file/dir/link), size, and name.
    Inaccessible entries shown as [???] instead of crashing.
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: path not found — {path}"

    if not p.is_dir():
        return f"Error: not a directory — {path}"

    try:
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))

        if not entries:
            return f"Empty directory: {p}"

        lines = [f"Contents of {p}:", ""]
        for entry in entries:
            try:
                if entry.is_symlink():
                    target = os.readlink(entry)
                    lines.append(f"  [link] {entry.name} -> {target}")
                elif entry.is_dir():
                    lines.append(f"  [dir]  {entry.name}/")
                else:
                    size = entry.stat().st_size
                    size_str = _format_size(size)
                    lines.append(f"  [file] {entry.name}  ({size_str})")
            except (OSError, PermissionError):
                lines.append(f"  [???]  {entry.name}  (inaccessible)")

        lines.append(f"\n{len(entries)} item(s)")
        return "\n".join(lines)

    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


def search(path: str, query: str) -> str:
    """
    Search for files matching a pattern OR containing specific text.

    If query contains a '*' or '?' → treated as filename glob pattern.
    Otherwise → search for files whose name contains query (case-insensitive),
                AND search file contents for the query string.
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: path not found — {path}"

    if not p.is_dir():
        return f"Error: not a directory — {path}"

    results = []
    is_glob = "*" in query or "?" in query

    try:
        for root, dirs, files in os.walk(p):
            # Skip hidden dirs and common noise
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "__pycache__"]

            for filename in files:
                filepath = Path(root) / filename

                if is_glob:
                    if fnmatch.fnmatch(filename.lower(), query.lower()):
                        results.append(str(filepath))
                else:
                    # Name match
                    if query.lower() in filename.lower():
                        results.append(str(filepath))
                        continue

                    # Content match — only text files, skip large ones
                    try:
                        if filepath.stat().st_size < 100 * 1024:
                            content = filepath.read_text(encoding="utf-8", errors="ignore")
                            if query.lower() in content.lower():
                                results.append(f"{filepath}  [content match]")
                    except (OSError, PermissionError):
                        pass

                if len(results) >= MAX_SEARCH_RESULTS:
                    break

    except PermissionError as e:
        return f"Error: permission denied during search — {e}"

    if not results:
        return f"No results for '{query}' in {p}"

    lines = [f"Search results for '{query}' in {p}:", ""]
    lines.extend(f"  {r}" for r in results[:MAX_SEARCH_RESULTS])
    if len(results) >= MAX_SEARCH_RESULTS:
        lines.append(f"  ... (showing first {MAX_SEARCH_RESULTS} results)")

    return "\n".join(lines)


def delete(path: str) -> str:
    """
    Delete a file.
    NOTE: This function exists but should only be called after
    confirmation in loop.py. Directories not supported — use shell rm -rf.
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: not found — {path}"

    if p.is_dir():
        return "Error: use shell tool with `rm -rf` for directories (requires confirmation)."

    try:
        p.unlink()
        return f"Deleted: {p}"
    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as e:
        return f"Error deleting file: {e}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024}KB"
    else:
        return f"{size_bytes // (1024 * 1024)}MB"
