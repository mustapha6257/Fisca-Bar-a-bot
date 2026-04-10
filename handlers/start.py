"""handlers/start.py — /start command and language selection."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.db import upsert_user, set_user_lang, get_user_lang
from utils.i18n import t, get_language_keyboard

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    upsert_user(user.id, username=user.username or "")

    keyboard = [
        [InlineKeyboardButton(label, callback_data=cb)]
        for label, cb in get_language_keyboard()
    ]
    await update.message.reply_text(
        "🔵🔴 *Culers Hub*\n\n🌐 Please choose your language / Choisissez votre langue / اختر لغتك:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cb_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = query.data.replace("lang_", "")
    chat_id = query.from_user.id
    set_user_lang(chat_id, lang)

    await query.edit_message_text(
        f"{t(lang, 'welcome', 'title')}\n\n{t(lang, 'welcome', 'body')}",
        parse_mode="HTML",
    )
    # Show main menu
    await _show_main_menu(query.message.chat_id, lang, ctx)


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_lang(update.effective_chat.id)
    await _show_main_menu(update.effective_chat.id, lang, ctx)


async def _show_main_menu(chat_id: int, lang: str, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    m = lambda key: t(lang, "menu", key)
    keyboard = [
        [InlineKeyboardButton(m("latest_news"),    callback_data="menu_news")],
        [InlineKeyboardButton(m("todays_match"),   callback_data="menu_match")],
        [InlineKeyboardButton(m("standings"),      callback_data="menu_standings")],
        [InlineKeyboardButton(m("live_subscribe"), callback_data="menu_subscribe")],
        [InlineKeyboardButton(m("change_language"),callback_data="menu_lang")],
    ]
    await ctx.bot.send_message(
        chat_id=chat_id,
        text=f"<b>{m('main_title')}</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
