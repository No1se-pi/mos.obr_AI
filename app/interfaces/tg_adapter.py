from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.singletons import get_scenario_service
from app.db.session import SessionLocal


URL_RE = re.compile(r"(?P<url>https?://[^\s<]+)")
PHONE_RE = re.compile(
    r"(?P<phone>(?:\+7|8)[\s\-]?(?:\(?\d{3}\)?[\s\-]?)\d{3}[\s\-]?\d{2}[\s\-]?\d{2})"
)
TELEGRAM_SAFE_TEXT_LIMIT = 3000
TELEGRAM_SAFE_HTML_LIMIT = 3900


@dataclass(slots=True)
class TgAnswer:
    text_html: str
    mode: str
    session_id: str | None
    suggestions: tuple[str, ...] = ()
    text_html_chunks: tuple[str, ...] = ()
    route: str | None = None
    step: str | None = None


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
        self.scenario_service = get_scenario_service()
        self.transcripts = SessionTranscriptStore(transcript_dir)

    def start_text_html(self) -> str:
        return (
            "Здравствуйте!\n\n"
            "Я AI-помощник по колледжам Москвы. Помогаю выбрать колледж или профессию, "
            "посмотреть специальности и разобраться с поступлением.\n\n"
            "Кто вы?"
        )

    def session_closed_text_html(self) -> str:
        return (
            "Сессию завершил.\n\n"
            "Когда захотите продолжить, нажмите /start."
        )

    def process_user_message(
        self,
        *,
        telegram_user_id: str,
        telegram_chat_id: str,
        telegram_username: str | None,
        user_text: str,
        session_id: str | None,
        action: str | None = None,
        callback_label: str | None = None,
    ) -> TgAnswer:
        service_message = user_text if action is None else ""
        logged_text = user_text or (f"[button] {callback_label or action}" if action else "")
        self.transcripts.append_event(
            platform_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            session_id=session_id,
            role="user",
            text=logged_text,
            extra={"action": action, "callback_label": callback_label} if action else None,
        )

        db = SessionLocal()
        try:
            result = self.scenario_service.ask(
                db=db,
                user_id=telegram_user_id,
                message=service_message,
                session_id=session_id,
                action=action,
                top_k=5,
            )
        finally:
            db.close()

        answer_text = str(result["answer"])
        answer_mode = str(result.get("dialog_mode", "unknown"))
        new_session_id = str(result.get("session_id") or session_id or "")
        suggestions = tuple(str(item) for item in (result.get("suggestions") or []) if str(item).strip())

        self.transcripts.append_event(
            platform_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_username=telegram_username,
            session_id=new_session_id,
            role="assistant",
            text=answer_text,
            mode=answer_mode,
            extra={
                "route": result.get("route"),
                "step": result.get("step"),
                "suggestions": list(suggestions),
            },
        )

        chunks = self.format_answer_chunks_html(answer_text)
        return TgAnswer(
            text_html=chunks[0] if chunks else "",
            mode=answer_mode,
            session_id=new_session_id or None,
            suggestions=suggestions,
            text_html_chunks=tuple(chunks),
            route=str(result.get("route") or "") or None,
            step=str(result.get("step") or "") or None,
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

    def format_answer_chunks_html(self, text: str) -> list[str]:
        chunks: list[str] = []
        for plain_chunk in self._split_plain_text_for_telegram(text):
            formatted = self.format_answer_html(plain_chunk)
            if len(formatted) <= TELEGRAM_SAFE_HTML_LIMIT:
                chunks.append(formatted)
                continue

            # Heavy link formatting can make HTML longer than the plain chunk.
            for smaller_chunk in self._split_plain_text_for_telegram(plain_chunk, max_chars=1500):
                chunks.append(self.format_answer_html(smaller_chunk))

        return chunks or [self.format_answer_html(text)]

    def _split_plain_text_for_telegram(
        self,
        text: str,
        *,
        max_chars: int = TELEGRAM_SAFE_TEXT_LIMIT,
    ) -> list[str]:
        text = self._cleanup_model_markdown(text)
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for block in self._iter_telegram_blocks(text, max_chars=max_chars):
            separator_len = 2 if current else 0
            if current and current_len + separator_len + len(block) > max_chars:
                chunks.append("\n\n".join(current).strip())
                current = [block]
                current_len = len(block)
                continue

            current.append(block)
            current_len += separator_len + len(block)

        if current:
            chunks.append("\n\n".join(current).strip())

        return [chunk for chunk in chunks if chunk]

    def _iter_telegram_blocks(self, text: str, *, max_chars: int) -> list[str]:
        blocks: list[str] = []
        for paragraph in re.split(r"\n{2,}", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) <= max_chars:
                blocks.append(paragraph)
                continue

            lines = paragraph.splitlines()
            if len(lines) > 1:
                blocks.extend(self._split_lines_for_telegram(lines, max_chars=max_chars))
            else:
                blocks.extend(self._split_long_line(paragraph, max_chars=max_chars))
        return blocks

    def _split_lines_for_telegram(self, lines: list[str], *, max_chars: int) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []
        current_len = 0

        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            if len(line) > max_chars:
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                    current_len = 0
                blocks.extend(self._split_long_line(line, max_chars=max_chars))
                continue

            separator_len = 1 if current else 0
            if current and current_len + separator_len + len(line) > max_chars:
                blocks.append("\n".join(current).strip())
                current = [line]
                current_len = len(line)
                continue

            current.append(line)
            current_len += separator_len + len(line)

        if current:
            blocks.append("\n".join(current).strip())

        return blocks

    def _split_long_line(self, line: str, *, max_chars: int) -> list[str]:
        parts: list[str] = []
        remaining = line.strip()
        while len(remaining) > max_chars:
            cut = remaining.rfind(" ", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            parts.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            parts.append(remaining)
        return parts

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
