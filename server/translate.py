"""
Merlin — Translation module
Provides LLM-based translation for real-time HUD subtitles.
"""

import logging

log = logging.getLogger("merlin.translate")

# Supported language codes
LANGUAGES = {
    "en": "English",
    "it": "Italian",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
}


async def translate_text(
    text: str,
    target_lang: str = "en",
    source_lang: str | None = None,
    backend=None,
) -> str:
    """
    Translate text using the configured LLM backend.
    Falls back to a simple identity if no backend is available.
    """
    if not text or not text.strip():
        return ""

    lang_name = LANGUAGES.get(target_lang, target_lang)

    if backend is None:
        return f"[translate to {lang_name}]: {text}"

    prompt = (
        f"Translate the following text to {lang_name}. "
        f"Respond with ONLY the translation, no commentary.\n\n{text}"
    )

    try:
        response = await backend.complete(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            system="You are a translation engine. Output ONLY the translated text.",
            max_tokens=len(text) * 2 + 50,
        )
        result = (response.text or "").strip()
        return result if result else text
    except Exception as e:
        log.warning("Translation failed: %s", e)
        return text
