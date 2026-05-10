from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import zipfile
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.logger import get_logger
from app.services.chat_service import ChatService

logger = get_logger(__name__)

SESSION_TTL_MINUTES = 30
DEMO_HTML_PATH = Path(__file__).with_name("demo_chat.html")
LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs"))

app = FastAPI(
    title="MosObr AI API",
    description="HTTP API для локального AI-помощника по колледжам Москвы.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass(slots=True)
class ApiSessionState:
    session_id: str | None
    last_activity: datetime


site_sessions: dict[str, ApiSessionState] = {}
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        logger.info("[API] Инициализация ChatService")
        _chat_service = ChatService()
    return _chat_service


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_expired(state: ApiSessionState) -> bool:
    return now_utc() - state.last_activity > timedelta(minutes=SESSION_TTL_MINUTES)


def get_effective_session_id(user_id: str, incoming_session_id: str | None) -> tuple[str | None, bool]:
    """
    Возвращает session_id, который надо передать в chat_service.
    Если старая API-сессия протухла, возвращает None, чтобы chat_service создал новую.
    """
    if incoming_session_id:
        state = site_sessions.get(user_id)
        if state and state.session_id == incoming_session_id and is_expired(state):
            logger.info("[API] Сессия user_id=%s истекла по TTL", user_id)
            site_sessions.pop(user_id, None)
            return None, True
        return incoming_session_id, False

    state = site_sessions.get(user_id)
    if not state:
        return None, False

    if is_expired(state):
        logger.info("[API] Сессия user_id=%s истекла по TTL", user_id)
        site_sessions.pop(user_id, None)
        return None, True

    return state.session_id, False


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="ID пользователя на сайте")
    message: str = Field(..., min_length=1, description="Сообщение пользователя")
    session_id: Optional[str] = Field(None, description="ID сессии, если уже есть")


class ChatResponse(BaseModel):
    session_id: str
    mode: str
    answer: str
    expired_previous_session: bool = False


class SessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    ok: bool
    message: str


@app.get("/api/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "mosobr-ai-api",
        "active_site_sessions": len(site_sessions),
        "session_ttl_minutes": SESSION_TTL_MINUTES,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    user_id = request.user_id.strip()
    message = request.message.strip()

    session_id, expired = get_effective_session_id(user_id, request.session_id)

    logger.info(
        "[API] /api/chat user_id=%s session_id=%s expired=%s message=%r",
        user_id,
        session_id,
        expired,
        message[:200],
    )

    db = SessionLocal()
    try:
        result = get_chat_service().ask(
            db=db,
            user_id=f"site:{user_id}",
            user_query=message,
            session_id=session_id,
            top_k=5,
        )
    finally:
        db.close()

    new_session_id = str(result["session_id"])
    site_sessions[user_id] = ApiSessionState(
        session_id=new_session_id,
        last_activity=now_utc(),
    )

    return ChatResponse(
        session_id=new_session_id,
        mode=str(result.get("dialog_mode", "unknown")),
        answer=str(result["answer"]),
        expired_previous_session=expired,
    )


@app.post("/api/session/close", response_model=SessionResponse)
def close_session(request: SessionRequest) -> SessionResponse:
    site_sessions.pop(request.user_id.strip(), None)
    return SessionResponse(ok=True, message="Сессия закрыта")


@app.post("/api/session/reset", response_model=SessionResponse)
def reset_session(request: SessionRequest) -> SessionResponse:
    site_sessions.pop(request.user_id.strip(), None)
    return SessionResponse(ok=True, message="Новая сессия будет создана при следующем сообщении")


@app.get("/api/demo", response_class=HTMLResponse)
def demo() -> HTMLResponse:
    if DEMO_HTML_PATH.exists():
        return HTMLResponse(DEMO_HTML_PATH.read_text(encoding="utf-8"))

    return HTMLResponse(
        "<h1>MosObr AI API</h1><p>Файл demo_chat.html не найден.</p>",
        status_code=200,
    )


@app.get("/api/logs/list")
def list_logs() -> dict:
    """
    Возвращает список файлов логов, которые доступны внутри контейнера API.
    """
    if not LOGS_DIR.exists():
        return {
            "logs_dir": str(LOGS_DIR),
            "exists": False,
            "files": [],
        }

    files = []
    for path in sorted(LOGS_DIR.rglob("*")):
        if not path.is_file():
            continue

        try:
            stat = path.stat()
            files.append(
                {
                    "path": str(path.relative_to(LOGS_DIR)),
                    "size_bytes": stat.st_size,
                }
            )
        except OSError:
            continue

    return {
        "logs_dir": str(LOGS_DIR),
        "exists": True,
        "files": files,
    }


@app.get("/api/logs/download")
def download_logs() -> FileResponse:
    """
    Упаковывает папку logs в zip и отдаёт файлом.
    Если логов ещё нет, всё равно отдаёт zip с README.txt.
    """
    tmp = tempfile.NamedTemporaryFile(
        prefix="mosobr_ai_logs_",
        suffix=".zip",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    tmp.close()

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if LOGS_DIR.exists():
            has_files = False
            for path in LOGS_DIR.rglob("*"):
                if not path.is_file():
                    continue

                has_files = True
                zip_file.write(path, arcname=str(path.relative_to(LOGS_DIR)))

            if not has_files:
                zip_file.writestr("README.txt", "Папка логов существует, но файлов логов пока нет.\n")
        else:
            zip_file.writestr(
                "README.txt",
                f"Папка логов не найдена внутри контейнера: {LOGS_DIR}\n",
            )

    return FileResponse(
        path=str(tmp_path),
        media_type="application/zip",
        filename="mosobr_ai_logs.zip",
    )
