# Translation Skill — Vashishtha

## Status
Offline translation engine (Argos Translate) not yet installed — ARM/Python 3.13 compile issues with dependencies (sentencepiece, llvmlite).

## Current Capability
Translation currently handled via LLM — use the `translate` tool directly. It calls `brain.call_simple()` internally and is accurate for all major languages.
For very long text (multi-page documents), break into chunks and translate each separately.

## Planned Engine — Argos Translate
When installed (Phase 5):
- Fully offline, no content filtering, no cloud calls
- 50+ languages, 100+ pairs
- Models: ~80MB per language pair, stored at ~/.argos-translate/
- Max 2 models loaded simultaneously (4GB RAM constraint)

## Translation Rules
- from_lang: auto-detect unless specified
- to_lang: check user preferences in memory first, default "hi"
- Confirm language pair before translating long text (>500 words)
- If detection confidence < 0.6 → tell user, ask to confirm
- Never translate: code blocks, URLs, proper nouns unless asked
- Pivot routing (non-direct pairs) → mention quality may vary

## User Preferences
Check memory for `translation_preferences` key before translating.
Update memory after session if user sets new preferences.
