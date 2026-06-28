from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
from app.services.scenario_service import END_SESSION_BUTTON, USER_TYPE_BUTTONS, action_for_label

try:
    from app.config import get_settings
except Exception:
    get_settings = None  # type: ignore


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

END_SESSION_TEXT = END_SESSION_BUTTON
WAIT_TEXT = "Подожди пару секунд, я ещё дописываю предыдущий ответ."
CALLBACK_PREFIX = "scn:"


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


def telegram_button_label(label: str) -> str:
    label = str(label)
    lowered = label.lower()
    if label == END_SESSION_TEXT:
        return "✅ Завершить сессию"
    if label == "Главное меню":
        return f"🏠 {label}"
    if label == "Назад":
        return f"↩️ {label}"
    if any(word in lowered for word in ["родитель", "абитуриент", "поступающий"]):
        return f"👤 {label}"
    if any(word in lowered for word in ["свой вопрос", "другой вопрос", "задать вопрос"]):
        return f"💬 {label}"
    if any(word in lowered for word in ["найти", "поиск", "изменить", "уточнить"]):
        return f"🔎 {label}"
    if any(word in lowered for word in ["контакт", "адрес"]):
        return f"📞 {label}"
    if "колледж" in lowered:
        return f"🎓 {label}"
    if any(word in lowered for word in ["профес", "специаль", "отрасл", "направление"]):
        return f"📚 {label}"
    if any(word in lowered for word in ["заявлен", "подать"]):
        return f"📨 {label}"
    if "документ" in lowered:
        return f"📄 {label}"
    if "срок" in lowered:
        return f"📅 {label}"
    if any(word in lowered for word in ["вступитель", "испытан", "экзам"]):
        return f"🧪 {label}"
    if any(word in lowered for word in ["овз", "специальные условия", "особые условия"]):
        return f"♿ {label}"
    if any(word in lowered for word in ["арм", "отсроч"]):
        return f"🛡️ {label}"
    if any(word in lowered for word in ["бюджет", "конкурс"]):
        return f"💰 {label}"
    if any(word in lowered for word in ["правила", "порядок поступления", "поступ"]):
        return f"📋 {label}"
    return label


def scenario_keyboard(
    suggestions: tuple[str, ...] | list[str],
    *,
    include_end: bool = True,
) -> tuple[InlineKeyboardMarkup, dict[str, str]]:
    rows: list[list[InlineKeyboardButton]] = []
    current: list[InlineKeyboardButton] = []
    callback_labels: dict[str, str] = {}

    for label in suggestions:
        if not label:
            continue
        action = action_for_label(str(label))
        callback_data = f"{CALLBACK_PREFIX}{action}"
        callback_labels[callback_data] = str(label)
        current.append(InlineKeyboardButton(telegram_button_label(str(label)), callback_data=callback_data))
        if len(current) == 2:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    if include_end:
        callback_data = f"{CALLBACK_PREFIX}end_session"
        callback_labels[callback_data] = END_SESSION_TEXT
        rows.append([InlineKeyboardButton(telegram_button_label(END_SESSION_TEXT), callback_data=callback_data)])

    if not rows:
        callback_data = f"{CALLBACK_PREFIX}end_session"
        callback_labels[callback_data] = END_SESSION_TEXT
        rows = [[InlineKeyboardButton(telegram_button_label(END_SESSION_TEXT), callback_data=callback_data)]]
    return InlineKeyboardMarkup(rows), callback_labels


def remember_callback_labels(context: ContextTypes.DEFAULT_TYPE, labels: dict[str, str]) -> None:
    current = dict(context.user_data.get("callback_labels") or {})
    current.update(labels)
    context.user_data["callback_labels"] = current


def callback_action_is_button_only(action: str) -> bool:
    if action.startswith(("industry:", "pick:", "admission_topic:")):
        return True
    return action in {
        "set_user_type_parent",
        "set_user_type_applicant",
        "main_menu",
        "back",
        "route_college",
        "find_college",
        "help_choose_college",
        "college_contacts",
        "college_specialties",
        "college_admission",
        "college_question",
        "new_search",
        "show_more_colleges",
        "college_specialty_yes",
        "college_specialty_no",
        "college_specialty_unknown",
        "route_profession",
        "choose_industry",
        "know_profession",
        "unknown_profession",
        "profession_industry_interest",
        "show_colleges",
        "show_more_specialties",
        "route_admission",
        "other_admission_question",
        "route_custom",
    }


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
    context.user_data["session_id"] = None
    context.user_data["callback_labels"] = {}

    reply_markup, callback_labels = scenario_keyboard(USER_TYPE_BUTTONS, include_end=False)
    remember_callback_labels(context, callback_labels)

    await context.bot.send_message(
        chat_id=chat.id,
        text=adapter.start_text_html(),
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    context.user_data["dialog_active"] = True


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
            reply_markup, callback_labels = scenario_keyboard([], include_end=True)
            remember_callback_labels(context, callback_labels)
            await message.reply_text(WAIT_TEXT, reply_markup=reply_markup)
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
        return

    if not context.user_data.get("dialog_active"):
        await message.reply_text(
            "Сначала нажмите /start.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if is_generating(context):
        reply_markup, callback_labels = scenario_keyboard([], include_end=True)
        remember_callback_labels(context, callback_labels)
        await message.reply_text(WAIT_TEXT, reply_markup=reply_markup)
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
            reply_markup = None
            if is_last:
                reply_markup, callback_labels = scenario_keyboard(answer.suggestions, include_end=True)
                remember_callback_labels(context, callback_labels)
            await message.reply_text(
                text=chunk,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=False,
            )
    finally:
        set_generating(context, False)


async def callback_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    adapter = context.application.bot_data["chat_adapter"]
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat

    if query is None or user is None or chat is None:
        return

    await query.answer()
    data = query.data or ""
    if not data.startswith(CALLBACK_PREFIX):
        return

    action = data[len(CALLBACK_PREFIX):]
    label = str((context.user_data.get("callback_labels") or {}).get(data) or "")

    if action == "end_session":
        if is_generating(context):
            await query.answer(WAIT_TEXT, show_alert=False)
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
        context.user_data["callback_labels"] = {}

        if query.message:
            await query.message.reply_text(
                adapter.session_closed_text_html(),
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove(),
                disable_web_page_preview=True,
            )
        return

    if is_generating(context):
        await query.answer(WAIT_TEXT, show_alert=False)
        return

    context.user_data["dialog_active"] = True
    set_generating(context, True)

    try:
        if query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                logger.debug("Не удалось убрать inline-кнопки с прошлого сообщения", exc_info=True)

        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

        action_to_send = action if callback_action_is_button_only(action) else None
        user_text = "" if action_to_send else label
        answer = adapter.process_user_message(
            telegram_user_id=str(user.id),
            telegram_chat_id=str(chat.id),
            telegram_username=user.username,
            user_text=user_text,
            session_id=context.user_data.get("session_id"),
            action=action_to_send,
            callback_label=label,
        )
        context.user_data["session_id"] = answer.session_id
        context.user_data["last_mode"] = answer.mode

        chunks = answer.text_html_chunks or (answer.text_html,)
        for index, chunk in enumerate(chunks):
            is_last = index == len(chunks) - 1
            reply_markup = None
            if is_last:
                reply_markup, callback_labels = scenario_keyboard(answer.suggestions, include_end=True)
                remember_callback_labels(context, callback_labels)
            await context.bot.send_message(
                chat_id=chat.id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
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
        "Во время диалога выбирайте inline-кнопки сценария или нажмите «Завершить сессию».",
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
    application.add_handler(CallbackQueryHandler(callback_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    logger.info("Telegram bot started")
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
