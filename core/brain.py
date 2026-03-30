"""
brain.py — LLM Interface
Provider-agnostic brain. Supports Gemini, NVIDIA NIM, and Groq.
Switch providers via config.json "api.provider" field.
Nothing else in the codebase knows which LLM is running.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────

SKILLS_DIR  = Path(__file__).parent.parent / "skills"
CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# ── Skills config ─────────────────────────────────────────────────────────────
# All skills loaded always — keyword triggering removed.
# At ~10KB total, skills are negligible vs context window.
# Zero false negatives, zero latency overhead, zero classification errors.

_SKILLS_FILES = ["VASHISHTHA.md", "DEV.md", "DEVICE.md", "TRANSLATE.md", "DESIGN.md"]

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]

@dataclass
class BrainResponse:
    type: str                          # "text" | "tool_call" | "error"
    text: str | None = None
    tool_call: ToolCall | None = None
    thinking: str | None = None        # reasoning trace from thinking models
    raw: Any = None
    error: str | None = None


# ── Config loader ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


# ── Skills loader ─────────────────────────────────────────────────────────────

def _load_skills() -> str:
    """Load all skill files. No keyword matching, no false negatives."""
    loaded = []
    for filename in _SKILLS_FILES:
        path = SKILLS_DIR / filename
        if path.exists():
            loaded.append(path.read_text())
    return "\n\n---\n\n".join(loaded)


# ── System prompt ─────────────────────────────────────────────────────────────

AGENT_INSTRUCTIONS = """
You are Vashishtha, a sovereign personal agent running on a rooted Android device via Termux.

## How you operate
You work in a loop: think → use a tool → observe the result → think again → repeat until done.
When you have enough information or have completed the task, respond with plain text.

## Tool use rules
- Use tools to actually DO things, not just describe what could be done
- One tool call at a time — observe the result before calling the next
- If a tool fails, understand why and try a different approach

## Decision rules
- Small + reversible task → execute immediately
- Ambiguous → ask ONE clarifying question, then execute
- Big / irreversible → always confirm with user before acting
- Never assume on destructive operations

## Response style
- Be direct and concise
- Report what you did and what the result was
- If something failed, say so clearly — never fabricate results
"""

_RAW_SYSTEM_PROMPT = (
    "You are a precise analytical assistant. "
    "Follow instructions exactly and respond only as instructed."
)

def _build_system_prompt(skills: str, long_term_summary: str = "") -> str:
    parts = [skills]
    if long_term_summary:
        parts.append(long_term_summary)
    parts.append(AGENT_INSTRUCTIONS)
    return "\n\n".join(parts)


# ── Providers ─────────────────────────────────────────────────────────────────

class GeminiProvider:
    """Google Gemini via google-genai SDK."""

    # Explicit type map — don't rely on string coercion
    _TYPE_MAP: dict[str, str] = {
        "string":  "STRING",
        "integer": "INTEGER",
        "number":  "NUMBER",
        "boolean": "BOOLEAN",
        "array":   "ARRAY",
        "object":  "OBJECT",
    }

    def __init__(self, model: str, max_tokens: int, temperature: float, config: dict | None = None, **kwargs):
        from google import genai
        from google.genai import types as gtypes

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set in .env")

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.gtypes = gtypes

        # thinking_enabled read from config for API consistency with NIM/Groq.
        # Not yet used by Gemini — future models may support it.
        thinking_cfg = (config or {}).get("thinking", {})
        self.thinking_enabled = thinking_cfg.get("enabled", False)

        print(f"[brain] Provider: Gemini — model: {self.model}")

    def call(self, system_prompt: str, messages: list[dict], tool_schemas: list[dict] | None) -> BrainResponse:
        from google.genai import types as gtypes

        tools = self._build_tools(tool_schemas) if tool_schemas else None
        contents = self._format_messages(messages)

        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=self.max_tokens,
            temperature=self.temperature,
            tools=tools,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return self._parse(response)
        except Exception as e:
            return BrainResponse(type="error", error=str(e))

    def _parse(self, response) -> BrainResponse:
        try:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    return BrainResponse(
                        type="tool_call",
                        tool_call=ToolCall(name=fc.name, args=dict(fc.args)),
                        raw=response,
                    )
            text = response.text
            if text:
                return BrainResponse(type="text", text=text.strip(), raw=response)
            return BrainResponse(type="error", error="Empty response from Gemini")
        except Exception as e:
            return BrainResponse(type="error", error=f"Gemini parse error: {e}")

    def _build_tools(self, tool_schemas: list[dict]):
        from google.genai import types as gtypes

        declarations = []
        for schema in tool_schemas:
            properties = {}
            for param_name, param_info in schema.get("parameters", {}).items():
                raw_type = param_info.get("type", "string").lower()
                gemini_type = self._TYPE_MAP.get(raw_type, "STRING")
                properties[param_name] = gtypes.Schema(
                    type=gemini_type,
                    description=param_info.get("description", ""),
                )
            declarations.append(gtypes.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=gtypes.Schema(
                    type="OBJECT",
                    properties=properties,
                    required=schema.get("required", list(properties.keys())),
                ),
            ))
        return [gtypes.Tool(function_declarations=declarations)]

    def _format_messages(self, messages: list[dict]):
        from google.genai import types as gtypes

        result = []
        for msg in messages:
            role    = msg["role"]
            content = msg["content"]

            if role == "assistant":
                role = "model"
            if role == "tool":
                result.append(gtypes.Content(
                    role="user",
                    parts=[gtypes.Part(text=f"[Tool result — {msg.get('tool_name', 'unknown')}]: {content}")]
                ))
                continue
            result.append(gtypes.Content(
                role=role,
                parts=[gtypes.Part(text=content)]
            ))
        return result


# ── OpenAI-compatible base (NIM + Groq share identical boilerplate) ───────────

class _OpenAICompatibleProvider:
    """
    Base for providers with OpenAI-compatible APIs.
    Subclasses set BASE_URL and ENV_VAR, and may override call() for extra features.
    """

    BASE_URL: str = ""
    ENV_VAR:  str = ""

    def __init__(self, model: str, max_tokens: int, temperature: float, **kwargs):
        from openai import OpenAI

        api_key = os.getenv(self.ENV_VAR)
        if not api_key:
            raise EnvironmentError(f"{self.ENV_VAR} not set in .env")

        self.client      = OpenAI(base_url=self.BASE_URL, api_key=api_key)
        self.model       = model
        self.max_tokens  = max_tokens
        self.temperature = temperature

        # All providers expose thinking_enabled — api.py checks hasattr, this makes it consistent
        self.thinking_enabled = False

    def call(self, system_prompt: str, messages: list[dict], tool_schemas: list[dict] | None) -> BrainResponse:
        formatted = self._format_messages(system_prompt, messages)
        tools     = self._build_tools(tool_schemas) if tool_schemas else None

        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=formatted,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        if tools:
            kwargs["tools"]       = tools
            kwargs["tool_choice"] = "auto"

        self._inject_extras(kwargs)

        try:
            response = self.client.chat.completions.create(**kwargs)
            return self._parse(response)
        except Exception as e:
            return BrainResponse(type="error", error=str(e))

    def _inject_extras(self, kwargs: dict) -> None:
        """Hook for subclasses to inject provider-specific request params."""
        pass

    def _parse(self, response) -> BrainResponse:
        try:
            choice  = response.choices[0]
            message = choice.message

            # Extract thinking — present on NIM + Groq qwen-qwq models
            thinking: str | None = None
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                thinking = message.reasoning_content
            elif hasattr(choice, "reasoning_content") and choice.reasoning_content:
                thinking = choice.reasoning_content

            if message.tool_calls:
                tc   = message.tool_calls[0]
                args = json.loads(tc.function.arguments)
                return BrainResponse(
                    type="tool_call",
                    tool_call=ToolCall(name=tc.function.name, args=args),
                    thinking=thinking,
                    raw=response,
                )

            if message.content:
                return BrainResponse(
                    type="text",
                    text=message.content.strip(),
                    thinking=thinking,
                    raw=response,
                )

            return BrainResponse(type="error", error=f"Empty response from {type(self).__name__}")
        except Exception as e:
            return BrainResponse(type="error", error=f"{type(self).__name__} parse error: {e}")

    def _build_tools(self, tool_schemas: list[dict]) -> list[dict]:
        tools = []
        for schema in tool_schemas:
            properties: dict[str, Any] = {}
            required = schema.get("required", [])
            for param_name, param_info in schema.get("parameters", {}).items():
                properties[param_name] = {
                    "type":        param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
            tools.append({
                "type": "function",
                "function": {
                    "name":        schema["name"],
                    "description": schema["description"],
                    "parameters": {
                        "type":       "object",
                        "properties": properties,
                        "required":   required,
                    },
                },
            })
        return tools

    def _format_messages(self, system_prompt: str, messages: list[dict]) -> list[dict]:
        result: list[dict] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role    = msg["role"]
            content = msg["content"]
            if role == "tool":
                result.append({
                    "role":    "user",
                    "content": f"[Tool result — {msg.get('tool_name', 'unknown')}]: {content}"
                })
            elif role == "assistant":
                result.append({"role": "assistant", "content": content})
            else:
                result.append({"role": "user", "content": content})
        return result


class NIMProvider(_OpenAICompatibleProvider):
    """NVIDIA NIM via OpenAI-compatible API. Supports thinking via extra_body."""

    BASE_URL = "https://integrate.api.nvidia.com/v1"
    ENV_VAR  = "NIM_API_KEY"

    def __init__(self, model: str, max_tokens: int, temperature: float, config: dict | None = None, **kwargs):
        super().__init__(model, max_tokens, temperature)

        thinking_cfg             = (config or {}).get("thinking", {})
        self.thinking_enabled    = thinking_cfg.get("enabled", False)
        self.thinking_max_tokens = thinking_cfg.get("max_tokens", 1024)

        status = "ON" if self.thinking_enabled else "OFF"
        print(f"[brain] Provider: NVIDIA NIM — model: {self.model} | thinking: {status}")

    def _inject_extras(self, kwargs: dict) -> None:
        if self.thinking_enabled:
            kwargs["extra_body"] = {
                "nvext": {
                    "thinking":            {"type": "enabled"},
                    "max_thinking_tokens": self.thinking_max_tokens,
                }
            }


class GroqProvider(_OpenAICompatibleProvider):
    """
    Groq via OpenAI-compatible API. Fast inference.
    Thinking supported on qwen-qwq-32b — returned as reasoning_content,
    no request-side flag needed (always on for that model).
    """

    BASE_URL = "https://api.groq.com/openai/v1"
    ENV_VAR  = "GROQ_API_KEY"

    def __init__(self, model: str, max_tokens: int, temperature: float, config: dict | None = None, **kwargs):
        super().__init__(model, max_tokens, temperature)
        # Inherit thinking_enabled from config — used by api.py / va for display gating
        thinking_cfg          = (config or {}).get("thinking", {})
        self.thinking_enabled = thinking_cfg.get("enabled", False)
        print(f"[brain] Provider: Groq — model: {self.model}")


# ── Brain ─────────────────────────────────────────────────────────────────────

PROVIDERS: dict[str, type] = {
    "gemini": GeminiProvider,
    "nim":    NIMProvider,
    "groq":   GroqProvider,
}

class Brain:
    """
    Provider-agnostic LLM interface.
    Switch providers via config.json "api.provider".
    Everything else in the codebase is provider-blind.
    """

    def __init__(self):
        self.config  = _load_config()
        api_cfg      = self.config.get("api", {})

        self.max_tokens  = api_cfg.get("max_tokens", 2048)
        self.temperature = api_cfg.get("temperature", 0.7)

        provider_name = api_cfg.get("provider", "gemini")
        models        = api_cfg.get("models", {})
        model         = models.get(provider_name, "gemini-2.0-flash")

        if provider_name not in PROVIDERS:
            raise ValueError(
                f"Unknown provider: '{provider_name}'. Choose from: {list(PROVIDERS.keys())}"
            )

        self.provider_name = provider_name
        self.model         = model
        self.provider      = PROVIDERS[provider_name](
            model=model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            config=self.config,
        )

    def call(
        self,
        messages: list[dict],
        tool_schemas: list[dict] | None = None,
        memory=None,
    ) -> BrainResponse:
        skills        = _load_skills()
        long_term     = memory.get_long_term_summary() if memory else ""
        system_prompt = _build_system_prompt(skills, long_term)
        return self.provider.call(system_prompt, messages, tool_schemas)

    def call_simple(self, prompt: str) -> str:
        """Full pipeline call — loads skills + memory summary. Use for user-facing responses."""
        result = self.call(messages=[{"role": "user", "content": prompt}])
        return result.text if result.type == "text" else f"Error: {result.error}"

    def call_raw(self, prompt: str) -> str:
        """
        Minimal internal LLM call — no skills, no memory, no identity context.
        Use for: command analysis, confirmation parsing, any internal reasoning
        that must not be influenced by agent identity or user context.
        """
        result = self.provider.call(
            system_prompt=_RAW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tool_schemas=None,
        )
        return result.text if result.type == "text" else f"Error: {result.error}"

    def switch_provider(self, provider_name: str) -> None:
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown provider: '{provider_name}'")

        models = self.config.get("api", {}).get("models", {})
        model  = models.get(provider_name, "gemini-2.0-flash")

        self.provider_name = provider_name
        self.model         = model
        self.provider      = PROVIDERS[provider_name](
            model=model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            config=self.config,
        )
        print(f"[brain] Switched to: {provider_name} — {model}")

    def switch_model(self, model_name: str) -> None:
        self.model          = model_name
        self.provider.model = model_name
        print(f"[brain] Model switched to: {model_name}")
