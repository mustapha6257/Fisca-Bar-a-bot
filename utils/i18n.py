"""
i18n.py — Localization helper.
Loads languages.json once at startup; never touches an AI model.
"""
import json
import logging
from pathlib import Path
from functools import lru_cache
from config import SUPPORTED_LANGS, DEFAULT_LANG

logger = logging.getLogger(__name__)

_LANG_FILE = Path(__file__).parent.parent / "languages.json"


@lru_cache(maxsize=1)
def _load_all() -> dict:
    with open(_LANG_FILE, encoding="utf-8") as f:
        return json.load(f)


def t(lang: str, *keys: str, **fmt) -> str:
    """
    Translate a dotted key path for a given language code.

    Usage:
        t("en", "menu", "latest_news")          → "📰 Latest News"
        t("ar", "live", "broadcast_header",
          minute=55)                             → "🔴 تحديث مباشر — الدقيقة 55"
    """
    data = _load_all()
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    node = data[lang]
    try:
        for key in keys:
            node = node[key]
        return node.format(**fmt) if fmt else node
    except (KeyError, TypeError):
        # Graceful fallback to English
        try:
            node = data[DEFAULT_LANG]
            for key in keys:
                node = node[key]
            return node.format(**fmt) if fmt else node
        except Exception:
            return ".".join(keys)


def get_language_keyboard():
    """Returns list of (display_label, callback_data) tuples for language picker."""
    data = _load_all()
    return [
        (f"{data[code]['meta']['flag']} {data[code]['meta']['name']}", f"lang_{code}")
        for code in SUPPORTED_LANGS
    ]
