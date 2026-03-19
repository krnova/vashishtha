"""
tools/code_runner.py — Sandboxed Code Runner
Execute code in an isolated proot sandbox with config-driven binary linking.
Supports Python, Node.js, Java (optional), and any language the user links in config.

Sandbox layout:
  ~/vashishtha/sandbox/
  ├── rootfs/          ← fake root (proot sees this as /)
  │   ├── bin/         ← symlinks to termux binaries (python3, node, etc.)
  │   ├── lib/         ← bind-mounted termux libs at runtime
  │   ├── tmp/         ← code files land here, cleaned after run
  │   ├── saved/       ← persisted code files (when save_as provided)
  │   └── home/        ← working dir inside sandbox
  └── .sandbox_ready   ← sentinel file — sandbox is initialized

Isolation model:
  - proot available → proper path isolation, process sees only sandbox FS
  - proot unavailable → subprocess fallback with restricted env + cwd confinement
  - Rooted device gains no extra isolation — proot is intentionally userspace
    so non-rooted users get identical behavior

Confirmation: execute_code always requires user confirmation via loop.py.
"""

import os
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


# ── Paths ─────────────────────────────────────────────────────────────────────

VASHISHTHA_DIR = Path(__file__).parent.parent
SANDBOX_DIR    = VASHISHTHA_DIR / "sandbox"
ROOTFS_DIR     = SANDBOX_DIR / "rootfs"
TMP_DIR        = ROOTFS_DIR / "tmp"
SAVED_DIR      = ROOTFS_DIR / "saved"
HOME_DIR       = ROOTFS_DIR / "home"
BIN_DIR        = ROOTFS_DIR / "bin"
LIB_DIR        = ROOTFS_DIR / "lib"
SENTINEL       = SANDBOX_DIR / ".sandbox_ready"

CONFIG_PATH    = VASHISHTHA_DIR / "config.json"

# Termux prefix — standard location
TERMUX_PREFIX  = Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"))
TERMUX_BIN     = TERMUX_PREFIX / "bin"
TERMUX_LIB     = TERMUX_PREFIX / "lib"


# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT  = 30       # seconds per execution
MAX_OUTPUT_CHARS = 8000     # truncate large outputs — RAM constraint

# Language alias → canonical binary name
LANGUAGE_ALIASES: dict[str, str] = {
    "python":     "python3",
    "python3":    "python3",
    "py":         "python3",
    "javascript": "node",
    "js":         "node",
    "node":       "node",
    "nodejs":     "node",
    "java":       "java",
}

# Binary → invocation template ({binary}, {file}, {dir}, {classname}, {javac} substituted)
LANGUAGE_INVOCATIONS: dict[str, str] = {
    "python3": "{binary} {file}",
    "node":    "{binary} {file}",
    "java":    "{javac} {file} && {binary} -cp {dir} {classname}",
}

# Minimal safe environment — nothing from host leaks in
SAFE_ENV = {
    "PATH":   "/bin:/usr/bin",
    "HOME":   "/home",
    "TMPDIR": "/tmp",
    "TERM":   "xterm",
    "LANG":   "en_US.UTF-8",
}


# ── Config ────────────────────────────────────────────────────────────────────

def _load_sandbox_config() -> dict:
    """Load sandbox section from config.json. Returns empty dict if missing."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            return cfg.get("sandbox", {})
    except Exception:
        pass
    return {}


def _get_timeout(cfg: dict) -> int:
    return int(cfg.get("timeout", DEFAULT_TIMEOUT))


def _get_binary_map(cfg: dict) -> dict[str, str]:
    """
    Returns {binary_name: real_path} from config.json sandbox.binaries.
    Falls back to auto-detecting common binaries from Termux prefix.
    """
    configured: dict = cfg.get("binaries", {})

    # Auto-detect common binaries from Termux if not explicitly configured
    for name in ["python3", "node", "java", "javac"]:
        if name not in configured:
            candidate = TERMUX_BIN / name
            if candidate.exists():
                configured[name] = str(candidate)

    resolved: dict[str, str] = {}
    for name, path in configured.items():
        p = Path(path)
        if p.exists():
            resolved[name] = str(p)
        else:
            print(f"[code_runner] ⚠ Binary not found, skipping: {name} → {path}")

    return resolved


def _get_lib_paths(cfg: dict) -> list[str]:
    """Returns list of lib dirs to expose inside sandbox."""
    configured: list = cfg.get("lib_paths", [])
    # Always include Termux lib — binaries are dynamically linked against it
    defaults = [str(TERMUX_LIB)]
    all_paths = defaults + [p for p in configured if p not in defaults]
    return [p for p in all_paths if Path(p).exists()]


# ── Sandbox setup ─────────────────────────────────────────────────────────────

def _init_sandbox(binary_map: dict[str, str]) -> None:
    """
    Create sandbox skeleton FS and symlink binaries into it.
    Idempotent — safe to call on every run.
    Re-links binaries if config changes.
    """
    for d in [
        TMP_DIR, SAVED_DIR, HOME_DIR, BIN_DIR, LIB_DIR,
        ROOTFS_DIR / "usr" / "bin",
        ROOTFS_DIR / "proc",
        ROOTFS_DIR / "dev",
        ROOTFS_DIR / "sys",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # Symlink configured binaries into sandbox/rootfs/bin/ and usr/bin/
    for name, real_path in binary_map.items():
        for bin_dir in [BIN_DIR, ROOTFS_DIR / "usr" / "bin"]:
            link = bin_dir / name
            # Remove stale link if target changed
            if link.is_symlink() and os.readlink(link) != real_path:
                link.unlink()
            if not link.exists() and not link.is_symlink():
                link.symlink_to(real_path)

    SENTINEL.touch()


def _clean_tmp() -> None:
    """
    Clean stale code/class files from sandbox tmp before each run.
    Called at the start of every execute_code() — ensures tmp is clean
    regardless of how the previous run ended (crash, timeout, proot failure).
    """
    if not TMP_DIR.exists():
        return
    for pattern in ["*.py", "*.js", "*.java", "*.class"]:
        for f in TMP_DIR.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass


def _available_languages(binary_map: dict[str, str]) -> list[str]:
    """
    Return deduplicated list of language aliases available.
    Checks binary_map (config + auto-detect) — used before sandbox init.
    """
    available = []
    seen_binaries: set[str] = set()
    for alias, binary in LANGUAGE_ALIASES.items():
        if binary in binary_map and binary not in seen_binaries:
            available.append(alias)
            seen_binaries.add(binary)
    return sorted(available)


def _available_languages_in_sandbox() -> list[str]:
    """
    Return languages actually linked inside sandbox/rootfs/bin/.
    Source of truth for what the sandbox can actually run right now.
    """
    if not BIN_DIR.exists():
        return []
    available = []
    seen: set[str] = set()
    for alias, binary in LANGUAGE_ALIASES.items():
        link = BIN_DIR / binary
        if link.exists() and binary not in seen:
            available.append(alias)
            seen.add(binary)
    return sorted(available)


# ── Code file helpers ─────────────────────────────────────────────────────────

def _ext_for(binary: str) -> str:
    return {"python3": ".py", "node": ".js", "java": ".java"}.get(binary, ".txt")


def _extract_java_classname(code: str) -> str:
    """Extract public class name from Java source. Defaults to 'Main'."""
    import re
    match = re.search(r"public\s+class\s+(\w+)", code)
    return match.group(1) if match else "Main"


def _write_code_file(language: str, code: str) -> Path:
    """Write code to a temp file in sandbox/rootfs/tmp/. Returns path."""
    binary = LANGUAGE_ALIASES.get(language.lower(), language)
    ext = _ext_for(binary)

    if binary == "java":
        filename = f"{_extract_java_classname(code)}{ext}"
    else:
        filename = f"run_{int(time.time() * 1000)}{ext}"

    code_file = TMP_DIR / filename
    code_file.write_text(code, encoding="utf-8")
    return code_file


# ── Command builders ──────────────────────────────────────────────────────────

def _check_proot() -> bool:
    return shutil.which("proot") is not None


def _build_proot_command(
    binary: str,
    code_file: Path,
    language: str,
    lib_paths: list[str],
    binary_map: dict[str, str],
) -> list[str]:
    """Build full proot command list for isolated execution."""
    sandbox_file = f"/tmp/{code_file.name}"

    cmd = [
        "proot",
        f"--rootfs={ROOTFS_DIR}",
        "--bind=/proc",
        "--bind=/dev",
        "--bind=/sys",
        "--cwd=/home",
        "--kill-on-exit",
    ]

    # Expose lib paths inside sandbox at their real paths
    for lib_path in lib_paths:
        cmd.append(f"--bind={lib_path}:{lib_path}")

    # Bind the code file into sandbox /tmp
    cmd.append(f"--bind={code_file}:{sandbox_file}")

    # Build exec portion
    if language == "java":
        javac_bin = binary_map.get("javac", "javac")
        classname = _extract_java_classname(code_file.read_text())
        exec_str = f'"/bin/{javac_bin}" "{sandbox_file}" && "/bin/java" -cp /tmp {classname}'
    else:
        invocation = LANGUAGE_INVOCATIONS.get(binary, "{binary} {file}")
        exec_str = invocation.format(
            binary=f"/bin/{binary}",
            file=sandbox_file,
            dir="/tmp",
            classname=code_file.stem,
            javac=f"/bin/{binary_map.get('javac', 'javac')}",
        )

    return cmd + ["/bin/sh", "-c", exec_str]


def _build_subprocess_command(
    binary: str,
    code_file: Path,
    language: str,
    binary_map: dict[str, str],
) -> list[str]:
    """Fallback: direct subprocess without proot."""
    real_binary = binary_map.get(binary, binary)

    if language == "java":
        javac = binary_map.get("javac", "javac")
        classname = _extract_java_classname(code_file.read_text())
        return [
            "/bin/sh", "-c",
            f'"{javac}" "{code_file}" && "{real_binary}" -cp "{code_file.parent}" {classname}',
        ]

    return [real_binary, str(code_file)]


# ── Execution ─────────────────────────────────────────────────────────────────

def _run(
    cmd: list[str],
    timeout: int,
    use_proot: bool,
    lib_paths: list[str],
) -> dict[str, Any]:
    """Run execution command. Returns {stdout, stderr, returncode, timed_out}."""
    env = SAFE_ENV.copy()

    if not use_proot:
        # Subprocess fallback — expose lib paths so dynamic linking works
        env["LD_LIBRARY_PATH"] = ":".join(lib_paths)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(HOME_DIR) if not use_proot else None,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "returncode": -1,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "timed_out": False,
        }


def _format_result(
    language: str,
    result: dict,
    elapsed_ms: int,
    saved_path: str | None,
    use_proot: bool,
) -> str:
    mode = "proot sandbox" if use_proot else "subprocess (proot unavailable)"
    lines = [f"[{language}] {elapsed_ms}ms | exit {result['returncode']} | {mode}"]

    if result["timed_out"]:
        lines.append("⚠ TIMED OUT — process killed")

    stdout = result["stdout"].strip()
    stderr = result["stderr"].strip()

    if stdout:
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n[truncated — {len(result['stdout'])} chars total]"
        lines.append(f"\nstdout:\n{stdout}")

    if stderr:
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + "\n[truncated]"
        lines.append(f"\nstderr:\n{stderr}")

    if not stdout and not stderr:
        lines.append("\n(no output)")

    if saved_path:
        lines.append(f"\nSaved: {saved_path}")

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def execute_code(language: str, code: str, save_as: str | None = None) -> str:
    """
    Execute code in an isolated proot sandbox.

    Args:
        language:  Language to run: python, javascript/node, java.
                   Must be in config.json sandbox.binaries or auto-detected from Termux.
        code:      Complete, self-contained source code. No stdin — do not use input().
        save_as:   Optional filename to persist in sandbox/saved/. e.g. "fib.py".
                   If None, file is deleted after execution.

    Returns:
        Formatted string with stdout, stderr, exit code, timing, and isolation mode.

    Notes:
        - Always requires user confirmation (registered in ALWAYS_CONFIRM_TOOLS).
        - Runs with empty environment — no API keys, no host paths visible.
        - Timeout enforced — infinite loops are killed.
    """
    if not language or not language.strip():
        return "Error: language required"
    if not code or not code.strip():
        return "Error: code is empty"

    language = language.lower().strip()
    binary = LANGUAGE_ALIASES.get(language)
    if binary is None:
        return f"Error: unsupported language '{language}'. Supported: {', '.join(sorted(LANGUAGE_ALIASES.keys()))}"

    cfg = _load_sandbox_config()
    timeout = _get_timeout(cfg)
    binary_map = _get_binary_map(cfg)
    lib_paths = _get_lib_paths(cfg)

    if binary not in binary_map:
        available = _available_languages(binary_map)
        return (
            f"Error: '{language}' binary not found.\n"
            f"Available: {', '.join(available) if available else 'none'}\n"
            f"Install via pkg or add path to config.json sandbox.binaries."
        )

    _init_sandbox(binary_map)
    _clean_tmp()                               # always start with clean tmp
    code_file = _write_code_file(language, code)

    # Optional save — copy before execution so it's preserved even on crash
    saved_path = None
    if save_as:
        safe_name = Path(save_as).name  # strip path traversal
        dest = SAVED_DIR / safe_name
        shutil.copy2(code_file, dest)
        saved_path = str(dest)

    use_proot = _check_proot()

    if use_proot:
        cmd = _build_proot_command(binary, code_file, language, lib_paths, binary_map)
    else:
        print("[code_runner] ⚠ proot not found — subprocess fallback")
        cmd = _build_subprocess_command(binary, code_file, language, binary_map)

    start = time.time()
    result = _run(cmd, timeout, use_proot, lib_paths)
    elapsed_ms = int((time.time() - start) * 1000)

    # Post-run cleanup — belt-and-suspenders after _clean_tmp on next run
    try:
        if code_file.exists():
            code_file.unlink()
        if binary == "java":
            for f in TMP_DIR.glob("*.class"):
                f.unlink()
    except Exception:
        pass

    return _format_result(language, result, elapsed_ms, saved_path, use_proot)


def list_saved() -> str:
    """List code files saved in sandbox/saved/."""
    if not SAVED_DIR.exists():
        return "No saved files — sandbox not initialized yet."
    files = sorted(SAVED_DIR.iterdir())
    if not files:
        return "No saved code files."
    lines = [f"Saved code files ({len(files)}):"]
    for f in files:
        lines.append(f"  {f.name}  ({f.stat().st_size}B)")
    return "\n".join(lines)


def sandbox_status() -> str:
    """Return sandbox state — actual sandbox contents, isolation mode, paths."""
    cfg = _load_sandbox_config()
    binary_map = _get_binary_map(cfg)
    proot = _check_proot()
    initialized = SENTINEL.exists()
    lib_paths = _get_lib_paths(cfg)

    # What's actually in the sandbox vs what's configured
    sandbox_langs = _available_languages_in_sandbox()
    configured_langs = _available_languages(binary_map)
    not_yet_linked = [l for l in configured_langs if l not in sandbox_langs]

    # Sandbox bin contents
    bin_links = []
    if BIN_DIR.exists():
        for link in sorted(BIN_DIR.iterdir()):
            if link.is_symlink():
                target = os.readlink(link)
                bin_links.append(f"  {link.name} → {target}")

    lines = [
        f"Sandbox: {'initialized' if initialized else 'not initialized — will auto-init on first run'}",
        f"Path: {SANDBOX_DIR}",
        f"Isolation: {'proot' if proot else 'subprocess fallback (proot not found)'}",
        f"Timeout: {_get_timeout(cfg)}s",
        f"Lib paths bound: {len(lib_paths)}",
        "",
        f"Languages in sandbox: {', '.join(sandbox_langs) if sandbox_langs else 'none — run execute_code to init'}",
    ]

    if not_yet_linked:
        lines.append(f"Configured but not yet linked: {', '.join(not_yet_linked)}")

    if bin_links:
        lines.append("")
        lines.append("Binaries:")
        lines.extend(bin_links)

    return "\n".join(lines)
