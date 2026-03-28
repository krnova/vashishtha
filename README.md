# वशिष्ठ — Vashishtha

Sovereign personal agent. Runs on Android via Termux.  
Yours alone — no telemetry, no cloud lock-in, no BS.

---

## What it does

Vashishtha is an agentic LLM loop that runs on your phone. It can:
- Execute shell commands, read/write files, run code in a sandbox
- Search the web, deep-research topics, fetch pages
- Control your device — SMS, camera, notifications, clipboard, TTS, GPS
- Remember things across sessions (long-term memory)
- Translate text between languages
- Manage and work within your projects

---

## Setup

```bash
# 1. Clone
git clone https://github.com/krnova/vashishtha
cd vashishtha

# 2. Install
cp va $PREFIX/bin
va install
```

On first run, Vashishtha auto-detects root and termux-api availability and updates `config.json`.

### CLI — `va`

```bash
# Install the va binary
cp va $PREFIX/bin/va && chmod +x $PREFIX/bin/va

va run                        # start agent daemon
va stop                       # stop agent daemon
va restart                    # restart agent daemon
va status                     # daemon status + model info
va logs                       # tail agent logs (foreground)
va logs start                 # stream logs in background
va logs stop                  # stop background log stream
va logs clear                 # clear all logs

va query                      # interactive REPL (gold output)
va query -t                   # REPL with thinking traces
va query -v                   # REPL with verbose output
va query "your message"       # single query
va query -t "your message"    # single query with thinking
va query -v "your message"    # single query verbose

va new-session                # clear session
va session                    # show current session ID

va install                    # run the install script
```

---

## Root vs Non-root

Root is auto-detected at startup. Your feature set adjusts automatically.

| Feature | Non-rooted | Rooted |
|---|---|---|
| Shell commands | ✅ All standard commands | ✅ + `su -c` for root ops |
| File read/write | ✅ Termux home + storage | ✅ + system paths |
| Web search & research | ✅ | ✅ |
| Code execution (sandbox) | ✅ Alpine via proot-distro | ✅ Alpine via proot-distro |
| Translation | ✅ | ✅ |
| Memory | ✅ | ✅ |
| termux-api tools* | ✅ if installed | ✅ if installed |
| SMS / Camera / GPS | ✅ if termux-api installed | ✅ if termux-api installed |
| Root system commands | ❌ blocked | ✅ with confirmation |

*termux-api tools also auto-detected. Install with: `pkg install termux-api`

---

## Providers

Configure in `config.json`:

```json
"api": {
  "provider": "nim",
  "models": {
    "nim": "nvidia/nemotron-3-super-120b-a12b",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile"
  }
}
```

- **NIM** (default) — NVIDIA NIM API. Supports thinking mode (`-t` flag).
- **Gemini** — Google Gemini via `google-genai`.
- **Groq** — Fast inference via Groq API. OpenAI-compatible. `qwen-qwq-32b` supports thinking mode (`-t` flag).

Switch providers: change `provider` in `config.json`, restart.

---

## Linking Projects

Projects are symlinked into `projects/` and tracked in agent memory.

```bash
# Link a project
ln -s ~/myapp ~/vashishtha/projects/myapp

# Or just tell the agent:
va query "link my project myapp at ~/myapp"
# Agent creates the symlink and stores it in memory automatically
```

Memory structure per project:
```json
{
  "path": "~/vashishtha/projects/myapp",
  "status": "active",
  "stack": "React + TypeScript",
  "notes": "..."
}
```

List linked projects:
```bash
va query "list my projects"
```

---

## Code Execution

Code runs in an **isolated Alpine Linux container** via proot-distro — host filesystem completely hidden.

```bash
# One-time sandbox setup done with
va install

# Then just ask:
va query "run this python: print('hello')"
# Agent asks for confirmation, then executes in sandbox
```

Supported languages: Python, JavaScript (Node.js), Java.  
Agent can install additional Alpine packages autonomously via `apk add`.  
Check availability: `va query "sandbox status"`

---

## Structure

```
core/          LLM interface, agentic loop, memory, session state
tools/         All agent tools (web, shell, files, device, code, translate)
interface/     Voice (Phase 2), Web UI (Phase 3) — stubs
skills/        .md context files loaded into every system prompt
memory_store/  Session logs + long-term memory (gitignored)
sandbox/saved/ Persisted code files
projects/      Symlinks to managed projects
```

---

## Phases

- **Phase 1** ✅ — Core agent loop, tools, Flask API, memory, web search
- **Phase 2** 🔄 — Voice STT/TTS, device control
- **Phase 3** — Web UI, browser automation, Dhi integration
- **Phase 4** — Vector memory, semantic search, SQLite
- **Phase 5** — Local LLM, Argos Translate offline, native Android app
- **Phase 6** — Native Windows support (PowerShell CLI, Win32 paths, sandbox alternative to proot)
