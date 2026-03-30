# Dev Skill — Vashishtha

## Environment (Termux)
- Python 3.13, pip (always use `--break-system-packages`)
- Node.js, npm
- Git, GitHub CLI (`gh`) — authenticated
- No virtual envs needed — Termux is already isolated

## Vashishtha Project Structure
```
~/vashishtha/
├── core/          brain, loop, memory, context
├── tools/         all agent tools
├── interface/     voice (Phase 2), webui (Phase 3)
├── skills/        .md context files — loaded by brain
├── memory_store/  sessions + long_term.json
├── sandbox/
│   └── saved/     persisted code files (save_as param)
├── projects/      symlinks to managed projects
├── api.py         Flask REST API — port 5000
└── main.py        entry point
```

## Coding Conventions
- Python: type hints always, dataclasses for structured data
- Error handling: explicit try/except, never silent failures — return error strings from tools
- Never block main thread — use threading or subprocess for long tasks
- Imports: stdlib → third party → local, alphabetical within groups
- Constants: UPPER_SNAKE_CASE at module top

## Tool Development Pattern
New tool = one file in `tools/`, register in `tools/__init__.py` TOOLS dict + SCHEMAS list.
Schema must have: name, description, parameters, required.
Tool functions return strings always — agent reads string output.

## Code Execution Rules
- **ALWAYS use `execute_code` tool** — never use `write_file` + `shell` for running code
- Sandbox is an **isolated Alpine Linux container** via proot-distro
- Host filesystem completely hidden (`--isolated` flag) — no API keys, no host files visible inside
- Only `$TMPDIR/vashishtha_sandbox/` bind-mounted into container at `/sandbox`
- Languages available: python3, node, java — check `sandbox_status` if unsure
- `save_as` param to persist code in `sandbox/saved/`
- Code must be self-contained — no stdin

## Sandbox Bootstrap (one-time setup)
`va install` handles this automatically. Manual steps only if installing selectively:
```bash
pkg install proot-distro
proot-distro install alpine
proot-distro login alpine -- apk add python3 nodejs openjdk17
```

## Installing Packages in Sandbox
Install Alpine packages autonomously via shell tool — no confirmation needed, only affects container:
```bash
proot-distro login alpine -- apk add <package>
```
Examples: `apk add curl`, `apk add git`, `apk add gcc musl-dev`, `apk add rust`

**After installing** — binary availability is cached per-process. Restart the agent (`va restart`) or run `va query "sandbox status"` to trigger re-check.

## Project Linking
To link a project into Vashishtha:
```bash
# 1. Create symlink in projects/
ln -s ~/myapp ~/vashishtha/projects/myapp

# 2. Agent stores in long-term memory:
remember(
  key="project_myapp",
  value={"path": "~/vashishtha/projects/myapp", "status": "active", "stack": "..."},
  category="project",
  importance=2
)
```
- Key convention: `project_{name}`
- Path stored: symlink path (`~/vashishtha/projects/name`), not real path
- List projects: `list_memory(category="project")`

## Git Workflow
- Commit often, descriptive messages
- `git add . && git commit -m "type: description" && git push`
- Types: feat, fix, chore, refactor, docs
