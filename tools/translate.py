"""
tools/translate.py — Translation Tool
LLM-based translation with language detection.
Offline engine (Argos Translate) planned — blocked by ARM/Python 3.13 compile issues.

Current mode: LLM fallback via brain.call_simple()
Planned mode: Argos Translate (offline, uncensored, 50+ languages)
"""

from pathlib import Path
import json

# Brain injected at runtime
_brain = None

def init(brain_instance):
    """Inject brain for LLM-based translation."""
    global _brain
    _brain = brain_instance


# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def _load_translation_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                return json.load(f).get("translation", {})
    except Exception:
        pass
    return {}


# ── Language detection ────────────────────────────────────────────────────────

# Common language names → ISO codes
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

def _normalize_lang(lang: str) -> str:
    """Normalize language name/alias to code. Returns as-is if already a code."""
    if not lang:
        return "auto"
    l = lang.lower().strip()
    return _LANG_ALIASES.get(l, l)


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
        to_lang:   Target language. Name or ISO code (e.g. "hindi", "hi", "french", "fr").
                   Defaults to user preference from memory, then "hi".
        from_lang: Source language. "auto" to detect. Default: auto.

    Returns:
        Translated text, or error string.

    Note:
        Currently LLM-based. Argos Translate (offline) planned for Phase 5.
        LLM translation is accurate but requires cloud API call.
    """
    if not text or not text.strip():
        return "Error: empty text"

    if _brain is None:
        return "Error: brain not initialized — call translate.init(brain) at startup"

    cfg = _load_translation_config()

    # Resolve target language
    if not to_lang:
        to_lang = cfg.get("default_to", "hi")
    to_lang = _normalize_lang(to_lang)

    # Resolve source language
    from_lang = _normalize_lang(from_lang or cfg.get("default_from", "auto"))

    # Build prompt
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

    if result.startswith("Error:"):
        return result

    return result.strip()


def detect_language(text: str) -> str:
    """
    Detect the language of a given text.

    Args:
        text: Text to detect language of.

    Returns:
        Language name and ISO code, e.g. "Hindi (hi)".
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
    """List supported languages and current translation mode."""
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lang_display(code: str) -> str:
    """Return human-readable language name for a code."""
    _display = {
        "hi": "Hindi", "en": "English", "es": "Spanish",
        "fr": "French", "de": "German", "zh": "Chinese",
        "ja": "Japanese", "ar": "Arabic", "ru": "Russian",
        "pt": "Portuguese", "it": "Italian", "ko": "Korean",
    }
    return _display.get(code, code)
