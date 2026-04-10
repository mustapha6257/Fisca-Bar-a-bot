"""
gemini.py — Google Gemini Flash integration.
All calls are intentionally minimal to keep token costs low.
"""
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_WORDS

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_MODEL)

LANG_NAMES = {"en": "English", "ar": "Arabic", "fr": "French"}

# ─────────────────────────────────────────────────────────────
# LIVE COMMENTARY  (called only on Goal / Card / Sub events)
# ─────────────────────────────────────────────────────────────

COMMENTARY_PROMPT = """You are a passionate FC Barcelona commentator.
Rewrite the following match event as an excited fan in {lang_name}.
Use 🔵🔴 emojis. Keep it strictly under {max_words} words. No preamble.

Raw event JSON:
{event_json}"""


def generate_commentary(event_json: str, lang: str) -> str:
    """
    Generates one short commentary snippet for a match event.
    Returns empty string on failure so the caller can skip gracefully.
    """
    prompt = COMMENTARY_PROMPT.format(
        lang_name=LANG_NAMES.get(lang, "English"),
        max_words=GEMINI_MAX_WORDS,
        event_json=event_json,
    )
    try:
        response = _model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=80,       # ~25 words safety ceiling
                temperature=0.9,
            ),
        )
        text = response.text.strip()
        logger.info("Gemini commentary (%s): %s", lang, text[:60])
        return text
    except Exception as exc:
        logger.error("Gemini commentary error: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────
# NEWS SUMMARY  (called once per article, result cached)
# ─────────────────────────────────────────────────────────────

SUMMARY_PROMPT = """Summarise the following football news article in {lang_name}.
Write 2–3 engaging sentences as if you are a Barça fan journalist.
Add relevant emojis. No preamble.

Article:
{article_text}"""


def summarise_article(article_text: str, lang: str) -> str:
    prompt = SUMMARY_PROMPT.format(
        lang_name=LANG_NAMES.get(lang, "English"),
        article_text=article_text[:1500],   # truncate to save tokens
    )
    try:
        response = _model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=150,
                temperature=0.7,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini summary error: %s", exc)
        return ""
