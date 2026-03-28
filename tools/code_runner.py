"""
tools/code_runner.py — Sandboxed Code Runner
Executes code inside an isolated Alpine Linux container via proot-distro.

Sandbox model:
  - proot-distro + Alpine Linux ARM64
  - --isolated flag: host filesystem completely hidden from container
  - Only $TMPDIR/vashishtha_sandbox/ bind-mounted into container at /sandbox
  - No host binaries, no host libs, no host API keys visible inside
  - Alpine has its own Python, Node, Java via apk

Bootstrap (one-time):
  pkg install proot-distro
  proot-distro install alpine
  proot-distro login alpine -- apk add python3 nodejs openjdk17

Agent can install packages autonomously (no confirmation — only affects container):
  shell("proot-distro login alpine -- apk add <package>")

Confirmation: execute_code always requires user confirmation via loop.py.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path


# ── Module-level defaults (overridden by init()) ──────────────────────────────

DISTRO           = "alpine"
DEFAULT_TIMEOUT  = 30
MAX_OUTPUT_CHARS = 8_000

# ── Paths ─────────────────────────────────────────────────────────────────────

VASHISHTHA_DIR = Path(__file__).parent.parent
SAVED_DIR      = VASHISHTHA_DIR / "sandbox" / "saved"

TERMUX_PREFIX  = Path(os.environ.get("PREFIX",  "/data/data/com.termux/files/usr"))
TERMUX_TMPDIR  = Path(os.environ.get("TMPDIR",  "/data/data/com.termux/files/usr/tmp"))

# Host-side tmp — bind-mounted into Alpine at /sandbox
SANDBOX_TMP = TERMUX_TMPDIR / "vashishtha_sandbox"

# ── Language map ──────────────────────────────────────────────────────────────

# alias → (alpine_binary, file_extension)
LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    "python":     ("python3", ".py"),
    "python3":    ("python3", ".py"),
    "py":         ("python3", ".py"),
    "javascript": ("node",    ".js"),
    "js":         ("node",    ".js"),
    "node":       ("node",    ".js"),
    "nodejs":     ("node",    ".js"),
    "java":       ("java",    ".java"),
}

_APK_FOR: dict[str, str] = {
    "python3": "python3",
    "node":    "nodejs",
    "java":    "openjdk17",
}

# ── Binary availability cache ─────────────────────────────────────────────────
# Checking a binary inside Alpine spawns a full proot-distro container (~1-3s).
# Cache results per binary — invalidated when user installs new packages.

_binary_cache: dict[str, bool] = {}


def invalidate_binary_cache(binary: str | None = None) -> None:
    """
    Call after `proot-distro login alpine -- apk add <pkg>` to invalidate stale cache.
    Pass binary name to invalidate one entry, or None to clear all.
    """
    global _binary_cache
    if binary is None:
        _binary_cache = {}
        print("[code_runner] Binary cache cleared")
    elif binary in _binary_cache:
        del _binary_cache[binary]
        print(f"[code_runner] Binary cache invalidated: {binary}")


# ── Init (called from api.py) ─────────────────────────────────────────────────

def init(config: dict) -> None:
    """
    Inject config values. Called once at startup from api.py.
    Falls back to module-level defaults if not called.
    """
    global DISTRO, DEFAULT_TIMEOUT
    sandbox_cfg     = config.get("sandbox", {})
    DISTRO          = sandbox_cfg.get("distro",  DISTRO)
    DEFAULT_TIMEOUT = sandbox_cfg.get("timeout", DEFAULT_TIMEOUT)
    print(f"[code_runner] Sandbox: distro={DISTRO}, timeout={DEFAULT_TIMEOUT}s")


# ── Availability checks ───────────────────────────────────────────────────────

def _proot_distro_available() -> bool:
    return shutil.which("proot-distro") is not None


def _alpine_installed() -> bool:
    rootfs = TERMUX_PREFIX / "var" / "lib" / "proot-distro" / "installed-rootfs" / DISTRO
    return rootfs.exists()


def _check_binary_in_alpine(binary: str) -> bool:
    """Check if a binary exists inside the Alpine container. Result is cached."""
    if binary in _binary_cache:
        return _binary_cache[binary]
    try:
        result = subprocess.run(
            ["proot-distro", "login", DISTRO, "--isolated", "--", "which", binary],
            capture_output=True, text=True, timeout=15,
        )
        available = result.returncode == 0
    except Exception:
        available = False
    _binary_cache[binary] = available
    return available


# ── Bootstrap status ──────────────────────────────────────────────────────────

def _bootstrap_status() -> str:
    lines = []
    if not _proot_distro_available():
        lines.append("✗ proot-distro not installed")
        lines.append("  Fix: pkg install proot-distro")
        return "\n".join(lines)
    lines.append("✓ proot-distro available")
    if not _alpine_installed():
        lines.append(f"✗ {DISTRO} not installed")
        lines.append(f"  Fix: proot-distro install {DISTRO}")
        return "\n".join(lines)
    lines.append(f"✓ {DISTRO} installed")
    return "\n".join(lines)


# ── Sandbox setup ─────────────────────────────────────────────────────────────

def _init_sandbox() -> None:
    SANDBOX_TMP.mkdir(parents=True, exist_ok=True)
    SAVED_DIR.mkdir(parents=True, exist_ok=True)


def _clean_tmp() -> None:
    if not SANDBOX_TMP.exists():
        return
    for pattern in ("*.py", "*.js", "*.java", "*.class"):
        for f in SANDBOX_TMP.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass


# ── Code file helpers ─────────────────────────────────────────────────────────

def _extract_java_classname(code: str) -> str:
    import re
    match = re.search(r"public\s+class\s+(\w+)", code)
    return match.group(1) if match else "Main"


def _write_code_file(language: str, code: str) -> tuple[Path, str]:
    """Write code to host tmp. Returns (host_path, sandbox_path_inside_alpine)."""
    _, ext    = LANGUAGE_MAP[language]
    filename  = (
        f"{_extract_java_classname(code)}{ext}"
        if language == "java"
        else f"run_{int(time.time() * 1000)}{ext}"
    )
    host_path = SANDBOX_TMP / filename
    host_path.write_text(code, encoding="utf-8")
    return host_path, f"/sandbox/{filename}"


# ── Command builder ───────────────────────────────────────────────────────────

def _build_command(language: str, sandbox_path: str) -> list[str]:
    """
    Build the proot-distro invocation.
    --isolated: host filesystem completely hidden
    --bind:     only our code tmp dir visible inside, at /sandbox
    """
    binary, _ = LANGUAGE_MAP[language]

    base = [
        "proot-distro", "login", DISTRO,
        "--isolated",
        f"--bind={SANDBOX_TMP}:/sandbox",
        "--",
    ]

    if language == "java":
        classname = Path(sandbox_path).stem
        return base + ["sh", "-c", f"javac {sandbox_path} && java -cp /sandbox {classname}"]

    return base + [binary, sandbox_path]


# ── Execution ─────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "stdout":     result.stdout,
            "stderr":     result.stderr,
            "returncode": result.returncode,
            "timed_out":  False,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "returncode": -1, "timed_out": True}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "timed_out": False}


def _format_result(language: str, result: dict, elapsed_ms: int, saved_path: str | None) -> str:
    lines = [f"[{language}] {elapsed_ms}ms | exit {result['returncode']} | {DISTRO} (proot-distro, isolated)"]

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
    Execute code inside an isolated Alpine Linux container via proot-distro.

    Args:
        language: python, javascript/node, java
        code:     Complete, self-contained source. No stdin.
        save_as:  Optional filename to persist in sandbox/saved/.

    Notes:
        - Always requires user confirmation (ALWAYS_CONFIRM_TOOLS in loop.py).
        - Host filesystem completely hidden — --isolated flag.
        - Only $TMPDIR/vashishtha_sandbox/ visible inside at /sandbox.
        - To install missing languages: shell("proot-distro login alpine -- apk add <pkg>")
          then call invalidate_binary_cache() or restart.
    """
    if not language or not language.strip():
        return "Error: language required"
    if not code or not code.strip():
        return "Error: code is empty"

    language = language.lower().strip()
    if language not in LANGUAGE_MAP:
        supported = ", ".join(sorted(set(LANGUAGE_MAP.keys())))
        return f"Error: unsupported language '{language}'. Supported: {supported}"

    if not _proot_distro_available():
        return "Error: proot-distro not installed.\nFix: pkg install proot-distro"

    if not _alpine_installed():
        return f"Error: {DISTRO} not installed.\nFix: proot-distro install {DISTRO}"

    binary, _ = LANGUAGE_MAP[language]
    if not _check_binary_in_alpine(binary):
        pkg = _APK_FOR.get(binary, binary)
        return (
            f"Error: '{binary}' not found in {DISTRO}.\n"
            f"Fix: shell(\"proot-distro login {DISTRO} -- apk add {pkg}\")\n"
            f"Or ask me to install it — no confirmation needed for apk installs."
        )

    _init_sandbox()
    _clean_tmp()

    host_path, sandbox_path = _write_code_file(language, code)

    saved_path: str | None = None
    if save_as:
        dest       = SAVED_DIR / Path(save_as).name
        shutil.copy2(host_path, dest)
        saved_path = str(dest)

    cmd = _build_command(language, sandbox_path)

    start      = time.time()
    result     = _run(cmd, DEFAULT_TIMEOUT)
    elapsed_ms = int((time.time() - start) * 1000)

    # Cleanup host-side tmp
    try:
        host_path.unlink(missing_ok=True)
        for f in SANDBOX_TMP.glob("*.class"):
            f.unlink()
    except Exception:
        pass

    return _format_result(language, result, elapsed_ms, saved_path)


def list_saved() -> str:
    if not SAVED_DIR.exists():
        return "No saved files yet."
    files = sorted(SAVED_DIR.iterdir())
    if not files:
        return "No saved code files."
    lines = [f"Saved code files ({len(files)}):"]
    for f in files:
        lines.append(f"  {f.name}  ({f.stat().st_size}B)")
    return "\n".join(lines)


def sandbox_status() -> str:
    lines = [_bootstrap_status(), ""]

    if not _proot_distro_available() or not _alpine_installed():
        return "\n".join(lines)

    checked: set[str] = set()
    ready:   list[str] = []
    missing: list[str] = []

    for alias, (binary, _) in LANGUAGE_MAP.items():
        if binary in checked:
            continue
        checked.add(binary)
        if _check_binary_in_alpine(binary):
            ready.append(binary)
        else:
            missing.append(f"{binary} → apk add {_APK_FOR.get(binary, binary)}")

    if ready:
        lines.append(f"Languages ready:   {', '.join(ready)}")
    if missing:
        lines.append(f"Languages missing: {', '.join(missing)}")

    lines.append(f"\nCode tmp:  {SANDBOX_TMP}  (bind-mounted at /sandbox inside {DISTRO})")
    lines.append(f"Saved:     {SAVED_DIR}")
    lines.append(f"Isolation: --isolated (host filesystem fully hidden)")
    lines.append(f"Timeout:   {DEFAULT_TIMEOUT}s")

    return "\n".join(lines)
