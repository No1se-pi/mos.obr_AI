from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.singletons import get_chat_service
from app.db.session import SessionLocal


URL_RE = re.compile(r"(?P<url>https?://[^\s<]+)")
PHONE_RE = re.compile(
    r"(?P<phone>(?:\+7|8)[\s\-]?(?:\(?\d{3}\)?[\s\-]?)\d{3}[\s\-]?\d{2}[\s\-]?\d{2})"
)


@dataclass(slots=True)
class TgAnswer:
    text_html: str
    mode: str
    session_id: str | None


class SessionTranscriptStore:
    def __init__(self, base_dir: str = "logs/telegram_sessions") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def append_event(
        self,
        *,
        platform_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        session_id: str | None,
        role: str,
        text: str,
        mode: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "platform_user_id": platform_user_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_username": telegram_username,
            "session_id": session_id,
            "role": role,
            "mode": mode,
            "text": text,
            "extra": extra or {},
        }

        jsonl_path = self._jsonl_path(platform_user_id)
        txt_path = self._txt_path(platform_user_id)

        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        with txt_path.open("a", encoding="utf-8") as f:
            f.write(self._format_pretty_line(event) + "\n")

    def _jsonl_path(self, platform_user_id: str) -> Path:
        return self.base_dir / f"{self._safe_name(platform_user_id)}.jsonl"

    def _txt_path(self, platform_user_id: str) -> Path:
        return self.base_dir / f"{self._safe_name(platform_user_id)}.txt"

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)

    @staticmethod
    def _format_pretty_line(event: dict[str, Any]) -> str:
        ts = event["timestamp_utc"]
        role = event["role"]
        mode = event.get("mode") or "-"
        session_id = event.get("session_id") or "-"
        text = str(event["text"]).replace("\n", " ").strip()
        return f"[{ts}] [{session_id}] [{mode}] {role.upper()}: {text}"


class TelegramChatAdapter:
    def __init__(self, *, transcript_dir: str = "logs/telegram_sessions") -> None:
        self.chat_service = get_chat_service()
        self.transcripts = SessionTranscriptStore(transcript_dir)

    def start_text_html(self) -> str:
        return (
            "<b>Привет!</b>\n\n"
            "Я тестовый помощник по колледжам Москвы.\n\n"
            "<b>Что я умею:</b>\n"
            "• подобрать колледжи и специальности\n"
            "• ответить на вопросы про поступление\n"
            "• кратко объяснить, кем можно работать после обучения\n\n"
            "Нажми <b>«Начать диалог»</b> и просто напиши свой вопрос."
        )

    def session_closed_text_html(self) -> str:
        return (
            "Сессию завершил.\n\n"
            "Когда захочешь продолжить, просто нажми <b>«Начать диалог»</b>."
        )

    def process_user_message(
        self,
        *,
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        user_text: str,
        session_id: str | None,
    ) -> TgAnswer:
        self.transcripts.append_event(
            platform_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            session_id=session_id,
            role="user",
            text=user_text,
        )

        db = SessionLocal()
        try:
            result = self.chat_service.ask(
                db=db,
                user_id=telegram_user_id,
                user_query=user_text,
                session_id=session_id,
                top_k=5,
            )
        finally:
            db.close()

        answer_text = str(result["answer"])
        answer_mode = str(result.get("dialog_mode", "unknown"))
        new_session_id = str(result.get("session_id") or session_id or "")

        self.transcripts.append_event(
            platform_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            session_id=new_session_id,
            role="assistant",
            text=answer_text,
            mode=answer_mode,
        )

        return TgAnswer(
            text_html=self.format_answer_html(answer_text),
            mode=answer_mode,
            session_id=new_session_id or None,
        )

    def log_session_closed(
        self,
        *,
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        session_id: str | None,
    ) -> None:
        self.transcripts.append_event(
            platform_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            session_id=session_id,
            role="system",
            text="SESSION_CLOSED_BY_USER",
        )

    def format_answer_html(self, text: str) -> str:
        text = self._cleanup_model_markdown(text)
        escaped = html.escape(text.strip())
        escaped = self._linkify_urls(escaped)
        escaped = self._linkify_phones(escaped)
        return self._format_telegram_html(escaped)

    def _cleanup_model_markdown(self, text: str) -> str:
        text = text.replace("\r\n", "\n")
        text = text.replace("### ", "")
        text = text.replace("## ", "")
        text = text.replace("# ", "")
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"<(https?://[^>\s]+)>", r"\1", text)
        text = re.sub(r"https?://\S*\.\.\.", "", text)
        return text.strip()

    def _linkify_urls(self, escaped_text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            url = match.group("url")
            clean_url = url.rstrip(").,;]")
            suffix = url[len(clean_url):]
            return f'<a href="{clean_url}">{clean_url}</a>{suffix}'

        return URL_RE.sub(repl, escaped_text)

    def _linkify_phones(self, escaped_text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            phone = match.group("phone")
            normalized = re.sub(r"[^\d+]", "", phone)
            if normalized.startswith("8"):
                normalized = "+7" + normalized[1:]
            return f'<a href="tel:{normalized}">{phone}</a>'

        return PHONE_RE.sub(repl, escaped_text)

    def _format_telegram_html(self, escaped_text: str) -> str:
        lines = escaped_text.splitlines()
        formatted: list[str] = []
        in_quote_block = False

        for raw_line in lines:
            stripped = raw_line.strip()

            if not stripped:
                if in_quote_block:
                    formatted.append("")
                else:
                    formatted.append("")
                continue

            if self._is_heading(stripped):
                formatted.append(f"<b>{stripped.rstrip(':')}</b>")
                in_quote_block = False
                continue

            numbered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
            if numbered:
                content = numbered.group(2).strip()
                formatted.append(f"<b>{numbered.group(1)}.</b> {content}")
                in_quote_block = False
                continue

            if stripped.startswith("- "):
                bullet_text = stripped[2:].strip()
                if self._looks_like_address(bullet_text):
                    formatted.append(f"• <code>{bullet_text}</code>")
                else:
                    formatted.append(f"• {bullet_text}")
                continue

            if self._looks_like_specialty_line(stripped):
                formatted.append(f"<blockquote>{stripped}</blockquote>")
                in_quote_block = True
                continue

            if self._looks_like_address(stripped):
                formatted.append(f"<code>{stripped}</code>")
                in_quote_block = False
                continue

            formatted.append(stripped)
            in_quote_block = False

        text = "\n".join(formatted)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _is_heading(self, line: str) -> bool:
        heading_candidates = {
            "адреса:",
            "контакты:",
            "сайт:",
            "специальности:",
            "направления обучения:",
            "что здесь можно изучать:",
            "почему это подходит:",
            "следующий шаг:",
            "важные детали:",
            "контакты и дополнительная информация:",
            "программы обучения:",
            "почему колледж подойдет вам:",
            "заключение:",
        }
        normalized = line.lower().strip()
        return normalized in heading_candidates or (
            line.endswith(":") and len(line) <= 60 and not line.startswith("http")
        )

    def _looks_like_specialty_line(self, line: str) -> bool:
        lowered = line.lower()
        specialty_markers = (
            "разработка",
            "обеспечение информационной безопасности",
            "сетевое и системное администрирование",
            "компьютерные системы",
            "техническая эксплуатация",
            "графический дизайнер",
            "техника и искусство фотографии",
            "реклама",
            "дизайн",
        )
        return (
            len(line) <= 120
            and not line.startswith("•")
            and not line.startswith("http")
            and any(marker in lowered for marker in specialty_markers)
        )

    def _looks_like_address(self, line: str) -> bool:
        lowered = line.lower()
        markers = (
            "улиц",
            "просп",
            "шоссе",
            "переул",
            "бульвар",
            "д.",
            "дом ",
            "м. ",
            "москва",
            "проезд",
            "набереж",
        )
        return any(marker in lowered for marker in markers)
