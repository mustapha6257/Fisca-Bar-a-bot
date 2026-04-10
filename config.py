import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── Google Gemini ─────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-1.5-flash"          # cheapest + fastest

# ── API-Football (api-sports.io) ──────────────────────────
FOOTBALL_API_KEY  = os.getenv("FOOTBALL_API_KEY", "")
FOOTBALL_API_HOST = "v3.football.api-sports.io"
BARCELONA_TEAM_ID = 529
LA_LIGA_ID        = 140
UCL_ID            = 2
CURRENT_SEASON    = 2024

# ── Cache TTLs (seconds) ──────────────────────────────────
CACHE_TTL_STANDINGS = 3_600   # 1 hour
CACHE_TTL_NEWS      = 3_600   # 1 hour
CACHE_TTL_SCHEDULE  = 86_400  # 1 day

# ── Live-match settings ───────────────────────────────────
LIVE_POLL_INTERVAL     = 90    # seconds between API-Football polls
KICKOFF_NOTIFY_MINUTES = 15    # notify subscribers N mins before KO
GEMINI_MAX_WORDS       = 25    # commentary word cap

# ── RSS feeds ─────────────────────────────────────────────
RSS_FEEDS = [
    "https://www.mundodeportivo.com/rss/fc-barcelona",
    "https://www.sport.es/rss/fc-barcelona.xml",
]

# ── Supported languages ───────────────────────────────────
SUPPORTED_LANGS = ["en", "ar", "fr"]
DEFAULT_LANG    = "en"
