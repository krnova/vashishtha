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

# 2. Install dependencies
apt install python rust python-cryptography
pip install -r requirements.txt --break-system-packages

# 3. Configure
cp config.example.json config.json
cp .env.example .env
# Edit .env — add your NIM_API_KEY or GEMINI_API_KEY

# 4. Run
python main.py
```

On first run, Vashishtha auto-detects root and termux-api availability and updates `config.json`.

### CLI — `va`

```bash
# Install the va binary
cp va $PREFIX/bin/va && chmod +x $PREFIX/bin/va

va              # cd to vashishtha dir
va run          # start the agent
va query "your message"       # query (gold output)
va query -v "your message"    # full JSON response
va query -t "your message"    # with thinking traces
va new-session                # clear session
va session                    # show current session ID
```

---

## Root vs Non-root

Root is auto-detected at startup. Your feature set adjusts automatically.

| Feature | Non-rooted | Rooted |
|---|---|---|
| Shell commands | ✅ All standard commands | ✅ + `su -c` for root ops |
| File read/write | ✅ Termux home + storage | ✅ + system paths |
| Web search & research | ✅ | ✅ |
| Code execution (sandbox) | ✅ proot-based | ✅ proot-based |
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
    "gemini": "gemini-2.0-flash"
  }
}
```

- **NIM** (default) — NVIDIA NIM API. Supports thinking mode (`-t` flag).
- **Gemini** — Google Gemini via `google-genai`.

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

Code runs in an isolated proot sandbox — no access to your files or API keys.

```bash
va query "run this python: print('hello')"
# Agent asks for confirmation, then executes in sandbox
```

Supported languages: Python, JavaScript (Node.js), Java (if installed).  
Check availability: `va query "sandbox status"`

---

## Structure

```
core/          LLM interface, agentic loop, memory, session state
tools/         All agent tools (web, shell, files, device, code, translate)
interface/     Voice (Phase 2), Web UI (Phase 3) — stubs
skills/        .md context files loaded into every system prompt
memory_store/  Session logs + long-term memory (gitignored)
sandbox/       proot sandbox filesystem (gitignored)
projects/      Symlinks to managed projects
```

---

## Phases

- **Phase 1** ✅ — Core agent loop, tools, Flask API, memory, web search
- **Phase 2** 🔄 — Voice STT/TTS, device control
- **Phase 3** — Web UI, browser automation, Dhi integration
- **Phase 4** — Vector memory, semantic search, SQLite
- **Phase 5** — Local LLM, Argos Translate offline, native Android app
