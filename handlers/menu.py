"""handlers/menu.py — Handles all inline-button callbacks from the main menu."""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.db import get_user_lang, subscribe, unsubscribe
from utils.i18n import t
from services.football_api import get_standings, get_todays_match, get_fixture_lineups
from services.news_service import get_latest_articles, get_article_summary
from config import LA_LIGA_ID, UCL_ID

logger = logging.getLogger(__name__)

BACK_BTN = lambda lang: [[InlineKeyboardButton(t(lang, "menu", "back"),
                                                callback_data="menu_main")]]


# ─────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────

async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_user_lang(query.from_user.id)

    routes = {
        "menu_news":       _news,
        "menu_match":      _match,
        "menu_standings":  _standings,
        "menu_subscribe":  _subscribe,
        "menu_unsubscribe":_unsubscribe,
        "menu_lang":       _change_lang,
        "menu_main":       _main_menu,
    }
    handler = routes.get(data)
    if handler:
        await handler(query, lang, ctx)


# ─────────────────────────────────────────────────────────────
# NEWS
# ─────────────────────────────────────────────────────────────

async def _news(query, lang, ctx):
    await query.edit_message_text(t(lang, "news", "loading"))
    articles = get_latest_articles()

    if not articles:
        await query.edit_message_text(t(lang, "news", "no_news"),
                                      reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)))
        return

    lines = [f"<b>{t(lang, 'news', 'title')}</b>\n"]
    for i, art in enumerate(articles, 1):
        summary = await asyncio.to_thread(get_article_summary, art, lang)
        lines.append(
            f"<b>{i}. {art['title']}</b>\n"
            f"<i>{t(lang, 'news', 'ai_summary')}:</i> {summary}\n"
            f"<a href='{art['url']}'>{t(lang, 'news', 'read_more')}</a>\n"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)),
        disable_web_page_preview=True,
    )


# ─────────────────────────────────────────────────────────────
# MATCH
# ─────────────────────────────────────────────────────────────

async def _match(query, lang, ctx):
    await query.edit_message_text(t(lang, "match", "loading"))
    fixture_wrapper = get_todays_match()

    if not fixture_wrapper:
        await query.edit_message_text(
            t(lang, "match", "no_match"),
            reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)),
        )
        return

    fix    = fixture_wrapper.get("fixture", {})
    teams  = fixture_wrapper.get("teams", {})
    goals  = fixture_wrapper.get("goals", {})
    status = fix.get("status", {}).get("long", "")
    venue  = fix.get("venue", {}).get("name", "N/A")
    ref    = fix.get("referee", "TBC")

    home   = teams.get("home", {}).get("name", "")
    away   = teams.get("away", {}).get("name", "")
    h_goal = goals.get("home") if goals.get("home") is not None else "-"
    a_goal = goals.get("away") if goals.get("away") is not None else "-"

    # Lineups
    lineups = await asyncio.to_thread(get_fixture_lineups, fix.get("id"))
    lineup_text = ""
    if lineups:
        for team_name, ld in lineups.items():
            starters = [p["player"]["name"] for p in ld.get("startXI", [])]
            lineup_text += f"\n<b>{team_name}</b>\n" + ", ".join(starters)

    text = (
        f"<b>{home} vs {away}</b>\n"
        f"{t(lang, 'match', 'score')}: {h_goal} – {a_goal}  "
        f"[{status}]\n\n"
        f"{t(lang, 'match', 'venue')}: {venue}\n"
        f"{t(lang, 'match', 'referee')}: {ref}\n"
    )
    if lineup_text:
        text += f"\n<b>{t(lang, 'match', 'lineup')}</b>{lineup_text}"

    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)),
    )


# ─────────────────────────────────────────────────────────────
# STANDINGS
# ─────────────────────────────────────────────────────────────

def _render_table(standings_list: list, lang: str, max_rows: int = 10) -> str:
    s = t(lang, "standings")
    lines = [f"{'#':>2}  {'Team':<22} {'Pts':>3} {'W':>3} {'D':>3} {'L':>3} {'GD':>4}"]
    lines.append("─" * 42)
    for row in standings_list[:max_rows]:
        team  = row["team"]["name"][:20]
        stats = row["all"]
        gd    = row.get("goalsDiff", 0)
        gd_s  = f"+{gd}" if gd > 0 else str(gd)
        lines.append(
            f"{row['rank']:>2}  {team:<22} {row['points']:>3} "
            f"{stats['win']:>3} {stats['draw']:>3} {stats['lose']:>3} {gd_s:>4}"
        )
    return "<pre>" + "\n".join(lines) + "</pre>"


async def _standings(query, lang, ctx):
    la_liga = await asyncio.to_thread(get_standings, LA_LIGA_ID)
    ucl     = await asyncio.to_thread(get_standings, UCL_ID)

    parts = [f"<b>{t(lang, 'standings', 'title')}</b>\n"]
    if la_liga:
        parts.append(f"\n<b>{t(lang, 'standings', 'la_liga')}</b>")
        parts.append(_render_table(la_liga, lang))
    if ucl:
        parts.append(f"\n<b>{t(lang, 'standings', 'ucl')}</b>")
        parts.append(_render_table(ucl, lang, max_rows=8))

    if not la_liga and not ucl:
        parts.append(t(lang, "errors", "no_data"))

    await query.edit_message_text(
        "\n".join(parts), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)),
    )


# ─────────────────────────────────────────────────────────────
# SUBSCRIBE / UNSUBSCRIBE
# ─────────────────────────────────────────────────────────────

async def _subscribe(query, lang, ctx):
    newly = subscribe(query.from_user.id)
    key   = "subscribed" if newly else "already_subscribed"
    keyboard = [
        [InlineKeyboardButton(t(lang, "menu", "live_unsubscribe"),
                              callback_data="menu_unsubscribe")],
        *BACK_BTN(lang),
    ]
    await query.edit_message_text(
        t(lang, "live", key),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _unsubscribe(query, lang, ctx):
    done = unsubscribe(query.from_user.id)
    key  = "unsubscribed" if done else "not_subscribed"
    await query.edit_message_text(
        t(lang, "live", key),
        reply_markup=InlineKeyboardMarkup(BACK_BTN(lang)),
    )


# ─────────────────────────────────────────────────────────────
# CHANGE LANGUAGE
# ─────────────────────────────────────────────────────────────

async def _change_lang(query, lang, ctx):
    from utils.i18n import get_language_keyboard
    keyboard = [
        [InlineKeyboardButton(label, callback_data=cb)]
        for label, cb in get_language_keyboard()
    ] + BACK_BTN(lang)
    await query.edit_message_text(
        t(lang, "welcome", "language_prompt"),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _main_menu(query, lang, ctx):
    from handlers.start import _show_main_menu
    await query.delete_message()
    await _show_main_menu(query.message.chat_id, lang, ctx)
