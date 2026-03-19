# Translation Skill — Vashishtha

## Status
Offline translation engine (Argos Translate) not yet installed — ARM/Python 3.13 compile issues with dependencies (sentencepiece, llvmlite).

## Current Capability
Translation currently handled via LLM knowledge only — not offline.
For accurate translation of long text, use `deep_search` or `web_search` to find online translation resources.

## Planned Engine — Argos Translate
When installed:
- Fully offline, no content filtering, no cloud calls
- 50+ languages, 100+ pairs
- Models: ~80MB per language pair, stored at ~/.argos-translate/
- Max 2 models loaded simultaneously (4GB RAM constraint)

## Translation Rules (when engine available)
- from_lang: auto-detect unless specified
- to_lang: check user preferences in memory first, default "hi"
- Confirm language pair before translating long text (>500 words)
- If detection confidence < 0.6 → tell user, ask to confirm
- Never translate: code blocks, URLs, proper nouns unless asked
- Pivot routing (non-direct pairs) → mention quality may vary

## User Preferences
Check memory for `translation_preferences` key before translating.
Update memory after session if user sets new preferences.
