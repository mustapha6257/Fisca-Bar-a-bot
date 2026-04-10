"""
main.py — Culers Hub Bot entry point
=====================================
Starts the Telegram bot, registers all handlers,
and boots the APScheduler background jobs.
"""
import asyncio
import logging
from datetime import time as dt_time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN
from utils.db import init_db
from utils.cache import flush_all
import utils.cache as cache
from services.football_api import get_standings, get_todays_match
from services.match_tracker import init_tracker, run_match_tracker
from handlers.start import cmd_start, cb_language, cmd_menu
from handlers.menu import handle_menu
from config import LA_LIGA_ID, UCL_ID

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Background jobs ───────────────────────────────────────

async def job_refresh_standings():
    """Bust the standings cache so next request re-fetches."""
    logger.info("[SCHEDULER] Refreshing standings cache …")
    cache.delete(f"standings:{LA_LIGA_ID}")
    cache.delete(f"standings:{UCL_ID}")
    get_standings(LA_LIGA_ID)
    get_standings(UCL_ID)


async def job_refresh_schedule():
    """Re-fetch today's fixture once per day, then spin up live tracker."""
    logger.info("[SCHEDULER] Refreshing today's schedule …")
    from datetime import date
    cache.delete(f"fixture:{date.today().isoformat()}")
    fixture = get_todays_match()
    if fixture:
        logger.info("[SCHEDULER] Match found — starting live tracker.")
        asyncio.create_task(run_match_tracker())
    else:
        logger.info("[SCHEDULER] No match today.")


async def job_refresh_news():
    logger.info("[SCHEDULER] Busting news cache …")
    cache.delete("news:articles")


# ── Post-init hook ────────────────────────────────────────

async def post_init(app: Application) -> None:
    """Called once after the bot is fully initialised."""
    init_db()
    init_tracker(app.bot)

    scheduler = AsyncIOScheduler(timezone="Europe/Madrid")
    scheduler.add_job(job_refresh_standings, "interval", hours=1)
    scheduler.add_job(job_refresh_news,      "interval", hours=1)
    # Check for match at 06:00 Madrid time every day
    scheduler.add_job(job_refresh_schedule,  "cron",     hour=6, minute=0)
    scheduler.start()
    logger.info("Scheduler started.")

    # Warm up cache on startup
    await job_refresh_standings()
    await job_refresh_schedule()


# ── Main ──────────────────────────────────────────────────

def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_menu))

    # Language selection callback (from /start)
    app.add_handler(CallbackQueryHandler(cb_language, pattern=r"^lang_"))

    # All main-menu callbacks
    app.add_handler(CallbackQueryHandler(handle_menu, pattern=r"^menu_"))

    logger.info("Culers Hub Bot is running 🔵🔴")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
