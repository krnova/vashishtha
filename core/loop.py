"""
loop.py — Agentic Loop
The core of what makes Vashishtha an agent and not a chatbot.
plan → act → observe → repeat until done or confirmation needed.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.brain import Brain, BrainResponse
from tools import execute as tool_execute, get_schemas


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class LoopStep:
    iteration: int
    type: str                        # "tool_call" | "text" | "error"
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: str | None = None
    text: str | None = None
    error: str | None = None
    thinking: str | None = None      # reasoning trace from thinking models
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LoopResult:
    success: bool
    response: str
    steps: list[LoopStep]
    confirmation_required: bool = False
    confirmation_question: str | None = None
    pending_tool: str | None = None
    pending_args: dict | None = None
    iterations_used: int = 0

    # api.py compatibility aliases
    @property
    def status(self) -> str:
        if self.confirmation_required:
            return "confirm"
        return "done" if self.success else "error"

    @property
    def actions(self) -> list[dict]:
        result = []
        for s in self.steps:
            if s.type == "tool_call":
                action = {
                    "tool": s.tool_name,
                    "args": s.tool_args,
                    "result": s.tool_result,
                }
                if s.thinking:
                    action["thinking"] = s.thinking
                result.append(action)
        return result

    @property
    def thinking(self) -> str | None:
        """Thinking from the final step — what va and api.py surface as top-level thinking."""
        for s in reversed(self.steps):
            if s.thinking:
                return s.thinking
        return None

    @property
    def thinking_trace(self) -> list[dict]:
        """All thinking blocks across all steps — text, tool, error."""
        trace = []
        for s in self.steps:
            if s.thinking:
                trace.append({
                    "iteration": s.iteration,
                    "type": s.type,
                    "tool": s.tool_name,
                    "thinking": s.thinking,
                })
        return trace

    @property
    def confirm_question(self) -> str | None:
        return self.confirmation_question

    @property
    def pending_action(self) -> dict | None:
        if self.pending_tool:
            return {"tool": self.pending_tool, "args": self.pending_args}
        return None


# ── Confirmation rules ────────────────────────────────────────────────────────

# Tools that always require confirmation, no analysis needed
ALWAYS_CONFIRM_TOOLS = {"send_sms", "execute_code"}

# Instantly destructive shell patterns — no LLM analysis needed, always confirm
INSTANTLY_DESTRUCTIVE = [
    "rm ", "rm -", "rmdir", "mkfs", "dd ",
    "> /", "chmod", "chown", "kill ",
    "reboot", "shutdown", "format", "wipefs",
    "truncate", "shred", "mv /",
]


def _analyse_command(cmd: str, brain) -> tuple[bool, str]:
    """
    Ask LLM to reason about a command before deciding on confirmation.
    Returns (needs_confirmation: bool, reasoning: str).
    Internal — reasoning never shown to user directly, used to build prompt.
    """
    response = brain.call_raw(
        "You are a security-conscious system analyst. Analyze this shell command "
        "before it runs on a rooted Android device.\n\n"
        f"Command: {cmd}\n\n"
        "Think through:\n"
        "1. What will this command do exactly?\n"
        "2. What are its effects on files, system state, or data?\n"
        "3. Is it reversible? What would undoing it require?\n"
        "4. Could it cause data loss, system instability, or security risk?\n"
        "5. Is the risk significant enough to require user confirmation?\n\n"
        "After your analysis, end your response with exactly one of these two lines:\n"
        "VERDICT: YES\n"
        "VERDICT: NO\n\n"
        "YES = user must confirm before this runs\n"
        "NO = safe to execute without confirmation"
    )

    upper = response.upper()
    needs_conf = "VERDICT: YES" in upper
    reasoning = response.split("VERDICT:")[0].strip() if "VERDICT:" in upper else response.strip()
    return needs_conf, reasoning


def _needs_confirmation(tool_name: str, tool_args: dict, brain=None) -> tuple[bool, str]:
    """
    Returns (needs_confirmation: bool, reason: str).
    reason is used to build a better confirmation prompt for the user.
    """
    if tool_name in ALWAYS_CONFIRM_TOOLS:
        return True, "This tool always requires confirmation."

    if tool_name == "shell":
        cmd = tool_args.get("command", "").strip()

        # Instantly destructive — no LLM needed
        for kw in INSTANTLY_DESTRUCTIVE:
            if kw in cmd:
                return True, f"Command contains destructive operation: `{kw.strip()}`"

        # Root command — reason through it
        if cmd.startswith("su ") or "su -c" in cmd:
            if brain is None:
                return True, "Root command — no analysis available, confirming to be safe."
            needs_conf, reasoning = _analyse_command(cmd, brain)
            return needs_conf, reasoning

    if tool_name == "write_file":
        return True, "Writing to a file will overwrite existing content."

    return False, ""


def _confirmation_question(tool_name: str, tool_args: dict, reason: str = "") -> str:
    """Build a clear confirmation prompt, including analysis reasoning when available."""
    context = f"\n\n*Why:* {reason}" if reason else ""

    if tool_name == "shell":
        cmd = tool_args.get("command", "")
        return f"About to run:\n```\n{cmd}\n```{context}\n\nProceed? (yes/no)"

    if tool_name == "write_file":
        path = tool_args.get("path", "unknown")
        return f"About to write to `{path}`.{context}\n\nProceed? (yes/no)"

    if tool_name == "send_sms":
        number = tool_args.get("number", "unknown")
        msg = tool_args.get("message", "")
        return f"About to send SMS to {number}:\n\"{msg}\"{context}\n\nProceed? (yes/no)"

    if tool_name == "execute_code":
        lang = tool_args.get("language", "unknown")
        code = tool_args.get("code", "")
        save = tool_args.get("save_as")
        preview = code[:300] + ("..." if len(code) > 300 else "")
        save_note = f"\nWill be saved as: `{save}`" if save else "\nFile will be deleted after run."
        return (
            f"About to execute {lang} code in sandbox:\n"
            f"```{lang}\n{preview}\n```"
            f"{save_note}{context}\n\n"
            f"Proceed? (yes/no)"
        )

    return f"About to call `{tool_name}` with:\n```\n{json.dumps(tool_args, indent=2)}\n```{context}\n\nProceed? (yes/no)"


# ── Loop ──────────────────────────────────────────────────────────────────────

class Loop:
    """
    Agentic loop. One instance per session.
    Drives brain → tool → observe cycle until goal is met.
    """

    def __init__(self, brain: Brain, memory, context, max_iterations: int = 20):
        self.brain = brain
        self.memory = memory
        self.context = context
        self.max_iterations = brain.config.get("agent", {}).get("max_loop_iterations", max_iterations)

    def run(self, user_message: str) -> LoopResult:
        """Run the agentic loop for a user message."""

        self.memory.add_message(
            session_id=self.context.session_id,
            role="user",
            content=user_message,
        )

        steps: list[LoopStep] = []
        available_tools = get_schemas()
        last_tool_call: str | None = None  # repetition guard
        repeat_count: int = 0
        MAX_REPEATS = 3

        print(f"[loop] Starting — session: {self.context.session_id}")
        print(f"[loop] Tools: {[t['name'] for t in available_tools]}")

        for i in range(1, self.max_iterations + 1):
            print(f"[loop] Iteration {i}/{self.max_iterations}")

            history = self.memory.get_history(self.context.session_id)

            response: BrainResponse = self.brain.call(
                messages=history,
                tool_schemas=available_tools,
                memory=self.memory,
            )

            # ── Error ─────────────────────────────────────────────────────────
            if response.type == "error":
                steps.append(LoopStep(
                    iteration=i, type="error",
                    error=response.error,
                    thinking=response.thinking,
                ))
                error_msg = f"Something went wrong: {response.error}"
                self.memory.add_message(self.context.session_id, "assistant", error_msg)
                return LoopResult(success=False, response=error_msg, steps=steps, iterations_used=i)

            # ── Text — done ───────────────────────────────────────────────────
            if response.type == "text":
                steps.append(LoopStep(
                    iteration=i, type="text",
                    text=response.text,
                    thinking=response.thinking,
                ))
                self.memory.add_message(self.context.session_id, "assistant", response.text)
                print(f"[loop] Done after {i} iteration(s)")
                return LoopResult(success=True, response=response.text, steps=steps, iterations_used=i)

            # ── Tool call ─────────────────────────────────────────────────────
            if response.type == "tool_call":
                tool_name = response.tool_call.name
                tool_args = response.tool_call.args

                # Repetition guard — same tool+args repeated too many times
                call_sig = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                if call_sig == last_tool_call:
                    repeat_count += 1
                    if repeat_count >= MAX_REPEATS:
                        stuck_msg = f"Stuck in loop — same tool `{tool_name}` called {repeat_count} times with same args. Stopping."
                        print(f"[loop] ⚠ {stuck_msg}")
                        self.memory.add_message(self.context.session_id, "assistant", stuck_msg)
                        return LoopResult(success=False, response=stuck_msg, steps=steps, iterations_used=i)
                else:
                    last_tool_call = call_sig
                    repeat_count = 0

                print(f"[loop] Tool call: {tool_name}({json.dumps(tool_args)[:100]})")

                # ── Block root commands if root not available ──────────────────
                if tool_name == "shell":
                    cmd = tool_args.get("command", "").strip()
                    if cmd.startswith("su ") or "su -c" in cmd:
                        root_cfg = self.brain.config.get("device", {}).get("root_available", True)
                        if not root_cfg:
                            tool_result = (
                                "Error: root access not available on this device "
                                "(root_available=false in config.json). Cannot run su commands."
                            )
                            print(f"[loop] ✗ root blocked — {tool_result[:60]}")
                            steps.append(LoopStep(
                                iteration=i, type="tool_call",
                                tool_name=tool_name, tool_args=tool_args,
                                tool_result=tool_result,
                                thinking=response.thinking,
                            ))
                            self.memory.add_message(
                                session_id=self.context.session_id,
                                role="tool", content=tool_result, tool_name=tool_name,
                            )
                            continue

                needs_conf, reason = _needs_confirmation(tool_name, tool_args, self.brain)
                if needs_conf:
                    question = _confirmation_question(tool_name, tool_args, reason)
                    steps.append(LoopStep(
                        iteration=i, type="tool_call",
                        tool_name=tool_name, tool_args=tool_args,
                        thinking=response.thinking,
                    ))
                    print(f"[loop] Confirmation required")
                    return LoopResult(
                        success=True,
                        response=question,
                        steps=steps,
                        confirmation_required=True,
                        confirmation_question=question,
                        pending_tool=tool_name,
                        pending_args=tool_args,
                        iterations_used=i,
                    )

                # Execute tool
                start = time.time()
                try:
                    tool_result = str(tool_execute(tool_name, tool_args))
                except Exception as e:
                    tool_result = f"Tool error: {e}"
                elapsed = int((time.time() - start) * 1000)

                print(f"[loop] ✓ {tool_name} — {elapsed}ms — {tool_result[:80]}")

                steps.append(LoopStep(
                    iteration=i, type="tool_call",
                    tool_name=tool_name, tool_args=tool_args, tool_result=tool_result,
                    thinking=response.thinking,
                ))

                # Feed result back to memory so brain sees it next iteration
                self.memory.add_message(
                    session_id=self.context.session_id,
                    role="tool",
                    content=tool_result,
                    tool_name=tool_name,
                )
                continue

        # ── Iteration limit ───────────────────────────────────────────────────
        limit_msg = (
            f"Reached iteration limit ({self.max_iterations}). "
            f"Completed {len(steps)} step(s)."
        )
        self.memory.add_message(self.context.session_id, "assistant", limit_msg)
        return LoopResult(success=False, response=limit_msg, steps=steps, iterations_used=self.max_iterations)

    def run_confirmed(self, pending_action: dict) -> LoopResult:
        """Execute a confirmed pending action."""
        tool_name = pending_action["tool"]
        tool_args = pending_action.get("args", {})

        print(f"[loop] Executing confirmed: {tool_name}({tool_args})")

        start = time.time()
        try:
            tool_result = str(tool_execute(tool_name, tool_args))
        except Exception as e:
            tool_result = f"Tool error: {e}"
        elapsed = int((time.time() - start) * 1000)

        print(f"[loop] ✓ confirmed {tool_name} — {elapsed}ms")

        self.memory.add_message(
            session_id=self.context.session_id,
            role="tool",
            content=tool_result,
            tool_name=tool_name,
        )

        history = self.memory.get_history(self.context.session_id)
        response = self.brain.call(
            messages=history,
            memory=self.memory,
        )

        final_text = response.text if response.type == "text" else tool_result
        self.memory.add_message(self.context.session_id, "assistant", final_text)

        step = LoopStep(
            iteration=1, type="tool_call",
            tool_name=tool_name, tool_args=tool_args, tool_result=tool_result,
            thinking=response.thinking,
        )
        return LoopResult(success=True, response=final_text, steps=[step], iterations_used=1)
