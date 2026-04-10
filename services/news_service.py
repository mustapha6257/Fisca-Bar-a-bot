"""
news_service.py — RSS feed fetcher with per-article AI summarisation.
Summaries are cached per (article_url + lang) to avoid re-calling Gemini.
"""
import logging
import hashlib
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

import utils.cache as cache
from config import RSS_FEEDS, CACHE_TTL_NEWS
from services.gemini import summarise_article

logger = logging.getLogger(__name__)

MAX_ARTICLES = 5


def _fetch_article_body(url: str) -> str:
    """Best-effort scrape of article text (first 1500 chars)."""
    try:
        r = requests.get(url, timeout=8,
                         headers={"User-Agent": "CulersHubBot/1.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text() for p in paragraphs)[:1500]
    except Exception:
        return ""


def _cache_key_articles() -> str:
    return "news:articles"


def _summary_cache_key(url: str, lang: str) -> str:
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"news:summary:{url_hash}:{lang}"


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

def get_latest_articles() -> list[dict]:
    """
    Fetch and cache raw RSS items (no AI involved here).
    Returns list of {title, url, published, source}.
    """
    cached = cache.get(_cache_key_articles())
    if cached is not None:
        return cached

    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:MAX_ARTICLES]:
                articles.append({
                    "title":     entry.get("title", ""),
                    "url":       entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source":    feed.feed.get("title", "Barça News"),
                })
            if articles:
                break  # one source is enough; fallback to next if empty
        except Exception as exc:
            logger.warning("RSS feed error (%s): %s", feed_url, exc)

    articles = articles[:MAX_ARTICLES]
    cache.set(_cache_key_articles(), articles, CACHE_TTL_NEWS)
    return articles


def get_article_summary(article: dict, lang: str) -> str:
    """
    Returns AI summary for an article in the requested language.
    Cached per (url, lang) — Gemini is called at most once per article/language.
    """
    key    = _summary_cache_key(article["url"], lang)
    cached = cache.get(key)
    if cached:
        return cached

    body    = _fetch_article_body(article["url"]) or article["title"]
    summary = summarise_article(body, lang)
    if summary:
        cache.set(key, summary, CACHE_TTL_NEWS)
    return summary or article["title"]
