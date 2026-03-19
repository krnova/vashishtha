"""
api.py — Flask REST API
Local bridge between agent core and all interfaces (web UI, voice, mobile).
All interfaces are thin clients — they just hit these endpoints.
"""

from flask import Flask, request, jsonify
from dotenv import load_dotenv

from core.brain import Brain
from core.memory import Memory
from core.context import Context
from core.loop import Loop
from tools import memory_tool, web, translate

load_dotenv()

app = Flask(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────

brain = Brain()
memory = Memory(
    memory_window=brain.config.get("agent", {}).get("memory_window", 20)
)
memory_tool.init(memory)
web.init(brain)
translate.init(brain)

sessions: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_session(session_id: str | None) -> tuple[str, Context, Loop]:
    """Get existing session or create a new one. Loads from disk if needed."""
    if session_id and session_id in sessions:
        ctx = sessions[session_id]["context"]
        loop = sessions[session_id]["loop"]
        return session_id, ctx, loop

    # Try loading from disk — handles fresh process restarts
    if session_id and memory.load_session(session_id):
        ctx = Context(session_id=session_id)
        loop = Loop(brain=brain, memory=memory, context=ctx)
        sessions[session_id] = {"context": ctx, "loop": loop}
        print(f"[api] Restored session from disk: {session_id}")
        return session_id, ctx, loop

    # New session
    sid = memory.new_session()
    ctx = Context(session_id=sid)
    loop = Loop(brain=brain, memory=memory, context=ctx)
    sessions[sid] = {"context": ctx, "loop": loop}
    return sid, ctx, loop


def _parse_confirmation(message: str) -> bool | None:
    """
    Use LLM to determine if user is confirming or denying.
    Uses call_raw — no identity/skill context needed for this.
    Returns True (yes), False (no), or None (unclear).
    """
    prompt = f"""The user was asked to confirm or deny an action.
Their response was: "{message}"

Reply with exactly one word: YES or NO or UNCLEAR.
- YES if they are agreeing, confirming, or proceeding
- NO if they are refusing, cancelling, or saying no
- UNCLEAR if it cannot be determined"""

    result = brain.call_raw(prompt).strip().upper()
    if result.startswith("YES"):
        return True
    if result.startswith("NO"):
        return False
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "agent": "vashishtha",
        "model": brain.model,
        "active_sessions": len(sessions),
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    message = data.get("message", "").strip()
    session_id = data.get("session_id")
    confirming = data.get("confirming", False)
    force_thinking = data.get("thinking", False)

    if not message:
        return jsonify({"error": "message is required"}), 400

    # Per-request thinking override — wrapped in try/finally so it always restores
    _prev_thinking = None
    if force_thinking and hasattr(brain.provider, "thinking_enabled"):
        _prev_thinking = brain.provider.thinking_enabled
        brain.provider.thinking_enabled = True

    try:
        sid, ctx, loop = _get_or_create_session(session_id)

        # ── Confirmation flow ─────────────────────────────────────────────────
        if confirming and ctx.has_pending():
            confirmed = _parse_confirmation(message)
            if confirmed is True:
                result = loop.run_confirmed(ctx.pending_action)
                ctx.clear_pending()
            elif confirmed is False:
                ctx.clear_pending()
                memory.add_message(sid, "user", message)
                memory.add_message(sid, "assistant", "Action cancelled.")
                return jsonify({
                    "reply": "Action cancelled.",
                    "session_id": sid,
                    "status": "done",
                    "actions": [],
                    "thinking": None,
                    "confirmation_required": False,
                    "confirmation_question": None,
                    "pending_action": None,
                })
            else:
                # Unclear — ask again
                return jsonify({
                    "reply": "I couldn't tell if that was a yes or no. Please confirm: yes or no?",
                    "session_id": sid,
                    "status": "confirm",
                    "actions": [],
                    "thinking": None,
                    "confirmation_required": True,
                    "confirmation_question": ctx.pending_action,
                    "pending_action": ctx.pending_action,
                })
        else:
            result = loop.run(message)

    finally:
        # Always restore thinking state — even if something throws
        if _prev_thinking is not None:
            brain.provider.thinking_enabled = _prev_thinking

    # ── Confirmation needed ───────────────────────────────────────────────────
    if result.status == "confirm":
        ctx.set_pending(result.pending_action)
        return jsonify({
            "reply": result.response,
            "session_id": sid,
            "status": "confirm",
            "actions": result.actions,
            "thinking": result.thinking,
            "confirmation_required": True,
            "confirmation_question": result.confirm_question,
            "pending_action": result.pending_action,
        })

    # ── Done / error / limit ──────────────────────────────────────────────────
    return jsonify({
        "reply": result.response,
        "session_id": sid,
        "status": result.status,
        "actions": result.actions,
        "thinking": result.thinking,   # top-level thinking from final response
        "confirmation_required": False,
        "confirmation_question": None,
        "pending_action": None,
    })


@app.route("/session/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
        memory.clear_session(session_id)
        return jsonify({"status": "cleared", "session_id": session_id})
    return jsonify({"error": "session not found"}), 404


@app.route("/memory/long-term", methods=["GET"])
def get_long_term():
    return jsonify(memory.get_long_term())


@app.route("/memory/long-term", methods=["POST"])
def update_long_term():
    data = request.get_json(silent=True)
    if not data or "key" not in data or "value" not in data:
        return jsonify({"error": "key and value required"}), 400
    memory.update_long_term(data["key"], data["value"])
    return jsonify({"status": "updated", "key": data["key"]})


@app.route("/config", methods=["GET"])
def get_config():
    cfg = dict(brain.config)
    if "api" in cfg:
        cfg["api"] = {k: ("***" if k == "key" else v) for k, v in cfg["api"].items()}
    return jsonify(cfg)


# ── Entry point ───────────────────────────────────────────────────────────────

def start(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    print(f"[api] Vashishtha API starting on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)
