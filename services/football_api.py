"""
football_api.py — Wrapper around API-Football (api-sports.io).
Every public function checks the cache first; API is only hit when stale.
"""
import logging
from datetime import date
from typing import Optional

import requests

import utils.cache as cache
from config import (
    FOOTBALL_API_KEY, FOOTBALL_API_HOST,
    BARCELONA_TEAM_ID, LA_LIGA_ID, UCL_ID, CURRENT_SEASON,
    CACHE_TTL_STANDINGS, CACHE_TTL_SCHEDULE,
)

logger = logging.getLogger(__name__)

_BASE  = f"https://{FOOTBALL_API_HOST}"
_HEADERS = {
    "x-rapidapi-key":  FOOTBALL_API_KEY,
    "x-rapidapi-host": FOOTBALL_API_HOST,
}


def _get(endpoint: str, params: dict) -> Optional[dict]:
    """Raw GET with error handling."""
    try:
        r = requests.get(f"{_BASE}/{endpoint}", headers=_HEADERS,
                         params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            logger.warning("API-Football error: %s", data["errors"])
            return None
        return data
    except requests.RequestException as exc:
        logger.error("API-Football request failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
# STANDINGS  (cached 1 h)
# ─────────────────────────────────────────────────────────────

def get_standings(league_id: int) -> Optional[list]:
    key = f"standings:{league_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    data = _get("standings", {"league": league_id, "season": CURRENT_SEASON})
    if not data:
        return None

    try:
        standings = data["response"][0]["league"]["standings"][0]
        cache.set(key, standings, CACHE_TTL_STANDINGS)
        return standings
    except (IndexError, KeyError) as exc:
        logger.error("Standings parse error: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
# TODAY'S MATCH  (cached per day)
# ─────────────────────────────────────────────────────────────

def get_todays_match() -> Optional[dict]:
    today = date.today().isoformat()
    key   = f"fixture:{today}"
    cached = cache.get(key)
    if cached is not None:
        return cached  # may be the sentinel "NO_MATCH"

    data = _get("fixtures", {
        "team": BARCELONA_TEAM_ID,
        "date": today,
        "timezone": "Europe/Madrid",
    })
    if not data:
        return None

    fixtures = data.get("response", [])
    result   = fixtures[0] if fixtures else "NO_MATCH"
    cache.set(key, result, CACHE_TTL_SCHEDULE)
    return result if result != "NO_MATCH" else None


# ─────────────────────────────────────────────────────────────
# LIVE MATCH DATA  (never cached — called every LIVE_POLL_INTERVAL)
# ─────────────────────────────────────────────────────────────

def get_live_fixture(fixture_id: int) -> Optional[dict]:
    """Returns the full live fixture object (events, lineups, score)."""
    data = _get("fixtures", {"id": fixture_id, "timezone": "Europe/Madrid"})
    if not data or not data.get("response"):
        return None
    return data["response"][0]


def get_fixture_events(fixture_id: int) -> list[dict]:
    """Returns the events list for a fixture (goals, cards, subs)."""
    data = _get("fixtures/events", {"fixture": fixture_id})
    if not data:
        return []
    return data.get("response", [])


def get_fixture_lineups(fixture_id: int) -> Optional[dict]:
    """Returns both teams' lineups."""
    data = _get("fixtures/lineups", {"fixture": fixture_id})
    if not data or not data.get("response"):
        return None
    lineups = {}
    for team_data in data["response"]:
        lineups[team_data["team"]["name"]] = team_data
    return lineups
