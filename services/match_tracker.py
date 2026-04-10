"""
match_tracker.py — Master Match Tracker & Broadcast Engine
═══════════════════════════════════════════════════════════

Design goals
------------
1. Fetch-once-per-cycle  — API-Football is polled at most every
   LIVE_POLL_INTERVAL seconds (90 s default).
2. AI only on events    — Gemini is called ONLY when a NEW major
   event (Goal / Card / Substitution) is detected.
3. Generate once, broadcast many — One Gemini call per event,
   then the same text is sent to ALL subscribers, regardless of
   how many users are watching.
4. Per-language commentary — We generate ONE copy per language
   code present in the active subscriber list, not one per user.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

import utils.cache as cache
from utils.db import get_all_subscribers, get_user_lang
from utils.i18n import t
from services.football_api import (
    get_todays_match, get_live_fixture, get_fixture_events
)
from services.gemini import generate_commentary
from config import (
    TELEGRAM_BOT_TOKEN, LIVE_POLL_INTERVAL,
    KICKOFF_NOTIFY_MINUTES, SUPPORTED_LANGS,
)

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────
_seen_event_ids: set[int] = set()   # prevents duplicate broadcasts
_tracker_running: bool    = False
_bot: Optional[Bot]       = None

MAJOR_EVENT_TYPES = {"Goal", "Card", "subst"}


# ═════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════

def _format_score(fixture: dict) -> str:
    goals = fixture.get("goals", {})
    home  = goals.get("home", 0) or 0
    away  = goals.get("away", 0) or 0
    home_name = fixture["teams"]["home"]["name"]
    away_name = fixture["teams"]["away"]["name"]
    return f"{home_name} {home} – {away} {away_name}"


def _kickoff_dt(fixture: dict) -> Optional[datetime]:
    ts = fixture.get("fixture", {}).get("timestamp")
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _get_active_languages(subscriber_ids: list[int]) -> set[str]:
    """Return the set of language codes used by current subscribers."""
    langs = set()
    for cid in subscriber_ids:
        langs.add(get_user_lang(cid))
    return langs or {"en"}


# ═════════════════════════════════════════════════════════
# BROADCAST ENGINE
# ═════════════════════════════════════════════════════════

async def _broadcast(texts_by_lang: dict[str, str]) -> None:
    """
    Send a pre-generated message to every subscriber.
    texts_by_lang = { "en": "...", "ar": "...", "fr": "..." }

    Cost model:
        N subscribers, L unique languages → L Gemini calls (done upstream)
        Each user receives their own language's version.
        Telegram API calls = N (one per subscriber).
    """
    if not _bot:
        return

    subscribers = get_all_subscribers()
    if not subscribers:
        return

    for chat_id in subscribers:
        lang = get_user_lang(chat_id)
        text = texts_by_lang.get(lang) or texts_by_lang.get("en", "")
        if not text:
            continue
        try:
            await _bot.send_message(chat_id=chat_id, text=text,
                                    parse_mode="HTML")
            await asyncio.sleep(0.05)   # ~20 msg/s — stays well under TG limits
        except TelegramError as exc:
            logger.warning("Broadcast failed for %s: %s", chat_id, exc)


# ═════════════════════════════════════════════════════════
# AI COMMENTARY GENERATOR
# ═════════════════════════════════════════════════════════

async def _generate_and_broadcast_event(
    event: dict, active_langs: set[str], score_str: str, minute: str
) -> None:
    """
    For ONE event:
      1. Build commentary in each active language (Gemini call × len(active_langs)).
      2. Prepend a static header (no AI needed).
      3. Broadcast to all subscribers.
    """
    event_json = json.dumps(event, ensure_ascii=False)
    texts: dict[str, str] = {}

    for lang in active_langs:
        header = t(lang, "live", "broadcast_header", minute=minute)
        score_line = f"🔢 {score_str}"

        # AI commentary — the one and only Gemini call for this event+lang
        commentary = await asyncio.to_thread(
            generate_commentary, event_json, lang
        )

        if commentary:
            texts[lang] = f"{header}\n{score_line}\n\n{commentary}"
        else:
            # Fallback: plain static message if Gemini fails
            etype = event.get("type", "")
            static_key = {
                "Goal":  "goal" if event.get("team", {}).get("id") == 529 else "goal_against",
                "Card":  "yellow_card" if event.get("detail") == "Yellow Card" else "red_card",
                "subst": "substitution",
            }.get(etype, "broadcast_header")
            texts[lang] = f"{header}\n{score_line}\n\n{t(lang, 'live', static_key)}"

    await _broadcast(texts)


# ═════════════════════════════════════════════════════════
# MASTER MATCH TRACKER LOOP
# ═════════════════════════════════════════════════════════

async def run_match_tracker() -> None:
    """
    Main coroutine — runs in background.
    Lifecycle:
        1. Wait until today's fixture exists.
        2. Notify subscribers 15 min before KO.
        3. Poll live data every LIVE_POLL_INTERVAL seconds.
        4. On new major event → AI commentary → broadcast.
        5. Stop gracefully after Full Time.
    """
    global _tracker_running, _seen_event_ids

    if _tracker_running:
        logger.info("Tracker already running — skipping duplicate start.")
        return

    _tracker_running   = True
    _seen_event_ids    = set()
    notified_kickoff   = False
    match_finished     = False

    logger.info("Match tracker started.")

    try:
        while not match_finished:
            fixture_wrapper = get_todays_match()
            if not fixture_wrapper:
                logger.info("No fixture today — tracker sleeping 10 min.")
                await asyncio.sleep(600)
                continue

            fixture  = fixture_wrapper.get("fixture", {})
            fix_id   = fixture.get("id")
            status   = fixture.get("status", {}).get("short", "NS")
            ko_dt    = _kickoff_dt(fixture_wrapper)

            # ── 15-min kick-off notification ─────────────────────
            if not notified_kickoff and ko_dt:
                now       = datetime.now(tz=timezone.utc)
                wait_secs = (ko_dt - timedelta(minutes=KICKOFF_NOTIFY_MINUTES) - now).total_seconds()
                if 0 < wait_secs < 3600:
                    logger.info("Sleeping %.0f s until pre-KO notify.", wait_secs)
                    await asyncio.sleep(wait_secs)

                subscribers   = get_all_subscribers()
                active_langs  = _get_active_languages(subscribers)
                texts = {lang: _kickoff_message(fixture_wrapper, lang)
                         for lang in active_langs}
                await _broadcast(texts)
                notified_kickoff = True

            # ── Match not live yet ────────────────────────────────
            if status in ("NS", "TBD", "PST"):
                await asyncio.sleep(60)
                continue

            # ── Half-time pause ───────────────────────────────────
            if status == "HT":
                await asyncio.sleep(30)
                continue

            # ── Match finished ────────────────────────────────────
            if status in ("FT", "AET", "PEN", "AWD", "WO"):
                live = get_live_fixture(fix_id)
                score_str = _format_score(live) if live else ""
                subscribers  = get_all_subscribers()
                active_langs = _get_active_languages(subscribers)
                texts = {
                    lang: f"{t(lang, 'live', 'full_time')}\n🔢 {score_str}"
                    for lang in active_langs
                }
                await _broadcast(texts)
                match_finished = True
                logger.info("Match finished — tracker stopping.")
                break

            # ── LIVE: fetch events and detect new ones ─────────────
            live   = get_live_fixture(fix_id)
            events = get_fixture_events(fix_id)

            if not live or events is None:
                await asyncio.sleep(LIVE_POLL_INTERVAL)
                continue

            score_str    = _format_score(live)
            minute       = live.get("fixture", {}).get("status", {}).get("elapsed", "?")
            subscribers  = get_all_subscribers()
            active_langs = _get_active_languages(subscribers)

            for event in events:
                eid   = event.get("id") or id(event)    # fallback unique id
                etype = event.get("type", "")

                if eid in _seen_event_ids:
                    continue                             # already processed

                if etype not in MAJOR_EVENT_TYPES:
                    _seen_event_ids.add(eid)             # mark minor events too
                    continue

                # ✅ NEW major event — generate AI commentary once per language
                logger.info("New %s event detected (id=%s) at min %s",
                            etype, eid, minute)
                _seen_event_ids.add(eid)

                await _generate_and_broadcast_event(
                    event, active_langs, score_str, str(minute)
                )

            await asyncio.sleep(LIVE_POLL_INTERVAL)

    finally:
        _tracker_running = False
        logger.info("Match tracker stopped.")


# ═════════════════════════════════════════════════════════
# KICK-OFF NOTIFICATION MESSAGE
# ═════════════════════════════════════════════════════════

def _kickoff_message(fixture_wrapper: dict, lang: str) -> str:
    fix      = fixture_wrapper.get("fixture", {})
    teams    = fixture_wrapper.get("teams", {})
    venue    = fix.get("venue", {}).get("name", "")
    ref      = fix.get("referee", "TBC")
    home     = teams.get("home", {}).get("name", "")
    away     = teams.get("away", {}).get("name", "")
    ko_time  = datetime.fromtimestamp(
        fix.get("timestamp", 0), tz=timezone.utc
    ).strftime("%H:%M UTC")

    return (
        f"🔵🔴 {home} vs {away}\n"
        f"{t(lang, 'match', 'kickoff')}: {ko_time}\n"
        f"{t(lang, 'match', 'venue')}: {venue}\n"
        f"{t(lang, 'match', 'referee')}: {ref}\n\n"
        f"{t(lang, 'live', 'match_start')}"
    )


# ═════════════════════════════════════════════════════════
# INITIALISER — call once at bot startup
# ═════════════════════════════════════════════════════════

def init_tracker(bot: Bot) -> None:
    global _bot
    _bot = bot
