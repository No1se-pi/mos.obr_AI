from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.interfaces.tg_adapter import TelegramChatAdapter

try:
    from app.config import get_settings
except Exception:
    get_settings = None  # type: ignore


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

START_DIALOG_CALLBACK = "start_dialog"
END_SESSION_TEXT = "Закончить сессию"
WAIT_TEXT = "Подожди пару секунд, я ещё дописываю предыдущий ответ."


def load_bot_token() -> str:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()

    if get_settings is not None:
        try:
            settings = get_settings()
            for attr_name in ("telegram_bot_token", "bot_token", "telegram_token"):
                value = getattr(settings, attr_name, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except Exception as e:
            logger.warning("Не удалось получить токен через get_settings(): %s", e)

    raise RuntimeError(
        "Не найден TELEGRAM_BOT_TOKEN. Добавь TELEGRAM_BOT_TOKEN в .env или в настройки config.py."
    )


def start_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Начать диалог", callback_data=START_DIALOG_CALLBACK)]]
    )


def active_session_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(END_SESSION_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напиши свой вопрос…",
    )


def is_generating(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get("is_generating", False))


def set_generating(context: ContextTypes.DEFAULT_TYPE, value: bool) -> None:
    context.user_data["is_generating"] = value


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    adapter = context.application.bot_data["chat_adapter"]
    chat = update.effective_chat
    if chat is None:
        return

    context.user_data["dialog_active"] = False
    context.user_data["is_generating"] = False

    await context.bot.send_message(
        chat_id=chat.id,
        text=adapter.start_text_html(),
        parse_mode=ParseMode.HTML,
        reply_markup=start_inline_keyboard(),
        disable_web_page_preview=True,
    )


async def start_dialog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer()

    if is_generating(context):
        await query.message.reply_text(WAIT_TEXT)
        return

    context.user_data["dialog_active"] = True

    await query.message.reply_text(
        "Диалог начат. Напиши вопрос про колледжи, специальности или поступление.",
        reply_markup=active_session_keyboard(),
    )

    await query.message.reply_text(
        "Например:\n"
        "• Хочу стать ML-инженером, что посоветуешь?\n"
        "• Какие документы нужны для поступления?\n"
        "• Расскажи про колледжи для дизайнеров",
        disable_web_page_preview=True,
    )


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    adapter = context.application.bot_data["chat_adapter"]
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if message is None or user is None or chat is None or not message.text:
        return

    user_text = message.text.strip()

    if user_text == END_SESSION_TEXT:
        if is_generating(context):
            await message.reply_text(WAIT_TEXT, reply_markup=active_session_keyboard())
            return

        session_id = context.user_data.get("session_id")
        adapter.log_session_closed(
            telegram_user_id=str(user.id),
            telegram_chat_id=str(chat.id),
            telegram_username=user.username,
            session_id=session_id,
        )
        context.user_data["session_id"] = None
        context.user_data["dialog_active"] = False
        context.user_data["is_generating"] = False

        await message.reply_text(
            adapter.session_closed_text_html(),
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
            disable_web_page_preview=True,
        )
        await message.reply_text(
            "Когда будешь готов продолжить, нажми кнопку ниже.",
            reply_markup=start_inline_keyboard(),
        )
        return

    if not context.user_data.get("dialog_active"):
        await message.reply_text(
            "Сначала нажми «Начать диалог».",
            reply_markup=start_inline_keyboard(),
        )
        return

    if is_generating(context):
        await message.reply_text(WAIT_TEXT, reply_markup=active_session_keyboard())
        return

    set_generating(context, True)

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

        answer = adapter.process_user_message(
            telegram_user_id=str(user.id),
            telegram_chat_id=str(chat.id),
            telegram_username=user.username,
            user_text=user_text,
            session_id=context.user_data.get("session_id"),
        )
        context.user_data["session_id"] = answer.session_id
        context.user_data["last_mode"] = answer.mode

        chunks = answer.text_html_chunks or (answer.text_html,)
        for index, chunk in enumerate(chunks):
            is_last = index == len(chunks) - 1
            await message.reply_text(
                text=chunk,
                parse_mode=ParseMode.HTML,
                reply_markup=active_session_keyboard() if is_last else None,
                disable_web_page_preview=False,
            )
    finally:
        set_generating(context, False)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "Команды:\n"
        "/start — начать\n"
        "/help — подсказка\n\n"
        "Во время диалога можно нажать кнопку «Закончить сессию».",
        reply_markup=start_inline_keyboard(),
    )


def main() -> None:
    logger.info("Telegram bot bootstrap started")
    token = load_bot_token()
    logger.info("Telegram bot token loaded")

    application = ApplicationBuilder().token(token).build()
    logger.info("Telegram application built")

    application.bot_data["chat_adapter"] = TelegramChatAdapter()
    logger.info("Telegram chat adapter initialized")

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        CallbackQueryHandler(start_dialog_callback, pattern=f"^{START_DIALOG_CALLBACK}$")
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    logger.info("Telegram bot started")
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
