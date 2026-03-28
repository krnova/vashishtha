"""
tools/translate.py — Translation Tool
LLM-based translation with language detection.
Offline engine (Argos Translate) planned — blocked by ARM/Python 3.13 compile issues.

Current mode: LLM via brain.call_simple()
Planned mode: Argos Translate (offline, uncensored, 50+ languages)
"""

# Brain injected at runtime via init()
_brain = None

def init(brain_instance) -> None:
    """Inject brain. Called once at startup from api.py."""
    global _brain
    _brain = brain_instance


# ── Config access ─────────────────────────────────────────────────────────────
# Read config once from the injected brain — no repeated disk reads.

def _get_translation_config() -> dict:
    """
    Return the translation config section.
    Uses brain.config if available (injected at startup).
    Falls back to config.json if called before init() — should not happen in practice.
    """
    if _brain is not None:
        return _brain.config.get("translation", {})

    # Fallback for tests / cold import
    from pathlib import Path
    import json
    cfg_path = Path(__file__).parent.parent / "config.json"
    try:
        if cfg_path.exists():
            return json.loads(cfg_path.read_text()).get("translation", {})
    except Exception:
        pass
    return {}


# ── Language normalization ────────────────────────────────────────────────────

_LANG_ALIASES: dict[str, str] = {
    "hindi": "hi", "हिंदी": "hi",
    "english": "en",
    "spanish": "es", "español": "es",
    "french": "fr", "français": "fr",
    "german": "de", "deutsch": "de",
    "chinese": "zh",
    "japanese": "ja",
    "arabic": "ar",
    "russian": "ru",
    "portuguese": "pt",
    "italian": "it",
    "korean": "ko",
    "auto": "auto",
}

_LANG_DISPLAY: dict[str, str] = {
    "hi": "Hindi", "en": "English", "es": "Spanish",
    "fr": "French", "de": "German", "zh": "Chinese",
    "ja": "Japanese", "ar": "Arabic", "ru": "Russian",
    "pt": "Portuguese", "it": "Italian", "ko": "Korean",
}

def _normalize_lang(lang: str) -> str:
    if not lang:
        return "auto"
    return _LANG_ALIASES.get(lang.lower().strip(), lang.lower().strip())

def _lang_display(code: str) -> str:
    return _LANG_DISPLAY.get(code, code)


# ── Translation ───────────────────────────────────────────────────────────────

def translate(
    text: str,
    to_lang: str = "",
    from_lang: str = "auto",
) -> str:
    """
    Translate text to target language.

    Args:
        text:      Text to translate.
        to_lang:   Target language (name or ISO code). Defaults to user preference, then "hi".
        from_lang: Source language. "auto" to detect. Default: auto.
    """
    if not text or not text.strip():
        return "Error: empty text"

    if _brain is None:
        return "Error: brain not initialized — call translate.init(brain) at startup"

    cfg = _get_translation_config()

    to_lang   = _normalize_lang(to_lang or cfg.get("default_to", "hi"))
    from_lang = _normalize_lang(from_lang or cfg.get("default_from", "auto"))

    if from_lang == "auto":
        lang_instruction = f"Detect the source language and translate the following text to {_lang_display(to_lang)}."
    else:
        lang_instruction = f"Translate the following text from {_lang_display(from_lang)} to {_lang_display(to_lang)}."

    prompt = (
        f"{lang_instruction}\n\n"
        "Rules:\n"
        "- Output ONLY the translated text. No explanations, no preamble.\n"
        "- Preserve formatting, line breaks, and punctuation.\n"
        "- Do NOT translate: code blocks, URLs, proper nouns (unless clearly needed).\n"
        "- If text is already in the target language, return it unchanged.\n\n"
        f"Text to translate:\n{text}"
    )

    result = _brain.call_simple(prompt)
    return result.strip() if not result.startswith("Error:") else result


def detect_language(text: str) -> str:
    """
    Detect the language of a given text.
    Returns language name and ISO code, e.g. "Hindi (hi)".
    """
    if not text or not text.strip():
        return "Error: empty text"

    if _brain is None:
        return "Error: brain not initialized"

    prompt = (
        "Detect the language of the following text.\n"
        "Reply with ONLY: <language name> (<ISO 639-1 code>)\n"
        "Example: Hindi (hi) | English (en) | French (fr)\n\n"
        f"Text: {text[:500]}"
    )
    return _brain.call_raw(prompt).strip()


def supported_languages() -> str:
    lines = [
        "Translation mode: LLM-based (cloud)",
        "Argos Translate (offline): planned — blocked by ARM/Python 3.13 compile issues",
        "",
        "Supported languages (LLM mode): all major world languages",
        "Common targets: hi (Hindi), en (English), es (Spanish), fr (French),",
        "                de (German), zh (Chinese), ja (Japanese), ar (Arabic),",
        "                ru (Russian), pt (Portuguese), it (Italian), ko (Korean)",
        "",
        "Usage: translate(text, to_lang='hi', from_lang='auto')",
    ]
    return "\n".join(lines)
