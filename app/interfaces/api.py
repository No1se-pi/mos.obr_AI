from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import secrets
import tempfile
import time
import zipfile
from typing import Any, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

import app.db.chat_models  # noqa: F401 - registers chat tables
from app.db.chat_models import ensure_chat_session_runtime_schema
from app.config import get_settings
from app.db.session import SessionLocal
from app.db.repository import Document, create_tables
from app.db.session import engine
from app.logger import get_logger
from app.services.scenario_service import ScenarioService
from app.services.web_transcript_store import WebTranscriptStore

logger = get_logger(__name__)
settings = get_settings()

SESSION_TTL_MINUTES = 30
DEMO_HTML_PATH = Path(__file__).with_name("demo_chat.html")
WIDGET_JS_PATH = Path(__file__).with_name("mosobr-widget.js")
LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs"))
API_WAIT_FOR_DOCUMENTS = os.getenv("API_WAIT_FOR_DOCUMENTS", "1").strip().lower() not in {"0", "false", "no", "off"}
OLLAMA_HEALTH_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_HEALTH_TIMEOUT_SECONDS", "2"))

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

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


@app.on_event("startup")
def startup() -> None:
    wait_for_database()
    create_tables(engine)
    ensure_chat_session_runtime_schema(engine)
    if API_WAIT_FOR_DOCUMENTS:
        wait_for_documents()


def wait_for_database() -> None:
    attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "60"))
    delay = float(os.getenv("DB_WAIT_DELAY", "2"))

    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("[API] Database is ready")
            return
        except Exception as exc:
            logger.warning("[API] Database is not ready yet (%s/%s): %s", attempt, attempts, exc)
            time.sleep(delay)

    raise RuntimeError("Database did not become ready in time")


def get_document_counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        total = int(db.scalar(select(func.count()).select_from(Document)) or 0)
        faq = int(db.scalar(select(func.count()).select_from(Document).where(Document.doc_type == "faq")) or 0)
        college = int(db.scalar(select(func.count()).select_from(Document).where(Document.doc_type == "college")) or 0)
        specialty = int(db.scalar(select(func.count()).select_from(Document).where(Document.doc_type == "specialty")) or 0)
        return {
            "total": total,
            "faq": faq,
            "college": college,
            "specialty": specialty,
        }
    finally:
        db.close()


def check_database_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("[API] Health database check failed: %s", exc)
        return False


def documents_ready(counts: dict[str, int]) -> bool:
    return counts["faq"] > 0 and counts["college"] > 0 and counts["specialty"] > 0


def check_ollama_ready() -> bool:
    try:
        # Health must be cheap: /api/tags checks Ollama without text generation.
        url = f"{settings.ollama_host.rstrip('/')}/api/tags"
        response = requests.get(url, timeout=OLLAMA_HEALTH_TIMEOUT_SECONDS)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.info("[API] Ollama health check failed: %s", exc)
        return False


def wait_for_documents() -> None:
    attempts = int(os.getenv("API_DOCUMENT_WAIT_ATTEMPTS", "180"))
    delay = float(os.getenv("API_DOCUMENT_WAIT_DELAY", "2"))

    # API can start before ingest finishes, so we wait for all RAG document types.
    for attempt in range(1, attempts + 1):
        counts = get_document_counts()
        if counts["faq"] > 0 and counts["college"] > 0 and counts["specialty"] > 0:
            logger.info("[API] Documents are ready: %s", counts)
            return
        logger.warning("[API] Documents are not ready yet (%s/%s): %s", attempt, attempts, counts)
        time.sleep(delay)

    raise RuntimeError("Documents did not become ready in time")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def api_logs_enabled() -> bool:
    return env_flag("API_LOGS_ENABLED", default=False)


def api_logs_token() -> str:
    return os.getenv("API_LOGS_TOKEN", "").strip()


def require_logs_access(authorization: str | None = Header(default=None)) -> None:
    # Логи могут содержать реальные пользовательские сообщения, поэтому API-доступ закрыт по умолчанию.
    if not api_logs_enabled():
        raise HTTPException(status_code=403, detail="API logs are disabled")

    expected_token = api_logs_token()
    if not expected_token:
        return

    expected_header = f"Bearer {expected_token}"
    if not authorization or not secrets.compare_digest(authorization, expected_header):
        raise HTTPException(status_code=403, detail="Invalid API logs token")


@dataclass(slots=True)
class ApiSessionState:
    session_id: str | None
    last_activity: datetime


site_sessions: dict[str, ApiSessionState] = {}
_scenario_service: ScenarioService | None = None
_web_transcripts: WebTranscriptStore | None = None


def get_scenario_service() -> ScenarioService:
    global _scenario_service
    if _scenario_service is None:
        logger.info("[API] Инициализация ScenarioService")
        _scenario_service = ScenarioService()
    return _scenario_service


def get_web_transcripts() -> WebTranscriptStore:
    global _web_transcripts
    if _web_transcripts is None:
        _web_transcripts = WebTranscriptStore(LOGS_DIR / "web_sessions")
    return _web_transcripts


def append_web_event(
    *,
    site_user_id: str,
    session_id: str | None,
    role: str,
    text: str,
    mode: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    try:
        get_web_transcripts().append_event(
            site_user_id=site_user_id,
            session_id=session_id,
            role=role,
            text=text,
            mode=mode,
            extra=extra,
        )
    except Exception as exc:
        logger.warning("[API] Не удалось записать web transcript: %s", exc)


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
    route: Optional[str] = Field(None, description="Сценарный маршрут: college, profession, admission, custom")
    action: Optional[str] = Field(None, description="Сценарное действие или код нажатой кнопки")
    user_type: Optional[str] = Field(None, description="Тип пользователя: parent или applicant")


class SuggestionItem(BaseModel):
    label: str
    action: str


class ChatResponse(BaseModel):
    session_id: str
    mode: str
    answer: str
    route: Optional[str] = None
    step: Optional[str] = None
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    suggestion_labels: list[str] = Field(default_factory=list)
    expired_previous_session: bool = False


class SessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    ok: bool
    message: str


@app.get("/api/health")
def health() -> dict[str, str | int | bool]:
    database_ready = check_database_ready()
    try:
        counts = get_document_counts() if database_ready else {"total": -1, "faq": -1, "college": -1, "specialty": -1}
    except Exception:
        counts = {"total": -1, "faq": -1, "college": -1, "specialty": -1}
        database_ready = False

    docs_ready = documents_ready(counts)
    ollama_ready = check_ollama_ready()

    return {
        "status": "ok",
        "service": "mosobr-ai-api",
        "database_ready": database_ready,
        "documents_ready": docs_ready,
        "rag_ready": database_ready and docs_ready,
        "ollama_ready": ollama_ready,
        "ollama_model": settings.ollama_model,
        "active_site_sessions": len(site_sessions),
        "session_ttl_minutes": SESSION_TTL_MINUTES,
        "logs_dir": str(LOGS_DIR),
        "logs_dir_exists": int(LOGS_DIR.exists()),
        "web_logs_dir": str(LOGS_DIR / "web_sessions"),
        "web_logs_dir_exists": int((LOGS_DIR / "web_sessions").exists()),
        "api_logs_enabled": api_logs_enabled(),
        "api_logs_token_required": bool(api_logs_token()),
        "documents_total": counts["total"],
        "documents_faq": counts["faq"],
        "documents_college": counts["college"],
        "documents_specialty": counts["specialty"],
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
    append_web_event(
        site_user_id=user_id,
        session_id=session_id,
        role="user",
        text=message,
        extra={
            "incoming_session_id": request.session_id,
            "expired_previous_session": expired,
        },
    )

    try:
        db = SessionLocal()
        try:
            result = get_scenario_service().ask(
                db=db,
                user_id=f"site:{user_id}",
                message=message,
                session_id=session_id,
                route=request.route,
                action=request.action,
                user_type=request.user_type,
                top_k=5,
            )
        finally:
            db.close()
    except Exception as exc:
        append_web_event(
            site_user_id=user_id,
            session_id=session_id,
            role="system",
            text=f"ERROR: {exc}",
            mode="error",
            extra={"exception_type": type(exc).__name__},
        )
        raise

    new_session_id = str(result["session_id"])
    answer_mode = str(result.get("dialog_mode", "unknown"))
    answer_text = str(result["answer"])
    suggestions = [
        SuggestionItem(label=str(item.get("label") or ""), action=str(item.get("action") or ""))
        for item in (result.get("suggestion_buttons") or [])
        if isinstance(item, dict) and str(item.get("label") or "").strip()
    ]
    suggestion_labels = [str(item) for item in (result.get("suggestion_labels") or result.get("suggestions") or []) if str(item).strip()]
    site_sessions[user_id] = ApiSessionState(
        session_id=new_session_id,
        last_activity=now_utc(),
    )
    append_web_event(
        site_user_id=user_id,
        session_id=new_session_id,
        role="assistant",
        text=answer_text,
        mode=answer_mode,
        extra={"expired_previous_session": expired},
    )

    return ChatResponse(
        session_id=new_session_id,
        mode=answer_mode,
        answer=answer_text,
        route=result.get("route"),
        step=result.get("step"),
        suggestions=suggestions,
        suggestion_labels=suggestion_labels,
        expired_previous_session=expired,
    )


@app.post("/api/session/close", response_model=SessionResponse)
def close_session(request: SessionRequest) -> SessionResponse:
    user_id = request.user_id.strip()
    session_id = request.session_id or (site_sessions.get(user_id).session_id if site_sessions.get(user_id) else None)
    site_sessions.pop(user_id, None)
    append_web_event(
        site_user_id=user_id,
        session_id=session_id,
        role="system",
        text="SESSION_CLOSED_BY_USER",
        mode="session_close",
    )
    return SessionResponse(ok=True, message="Сессия закрыта")


@app.post("/api/session/reset", response_model=SessionResponse)
def reset_session(request: SessionRequest) -> SessionResponse:
    user_id = request.user_id.strip()
    session_id = site_sessions.get(user_id).session_id if site_sessions.get(user_id) else request.session_id
    site_sessions.pop(user_id, None)
    append_web_event(
        site_user_id=user_id,
        session_id=session_id,
        role="system",
        text="SESSION_RESET_BY_USER",
        mode="session_reset",
    )
    return SessionResponse(ok=True, message="Новая сессия будет создана при следующем сообщении")


@app.get("/api/demo", response_class=HTMLResponse)
def demo() -> HTMLResponse:
    if DEMO_HTML_PATH.exists():
        return HTMLResponse(DEMO_HTML_PATH.read_text(encoding="utf-8"))

    return HTMLResponse(
        "<h1>MosObr AI API</h1><p>Файл demo_chat.html не найден.</p>",
        status_code=200,
    )


@app.get("/static/mosobr-widget.js")
def widget_js() -> FileResponse:
    if not WIDGET_JS_PATH.exists():
        raise HTTPException(status_code=404, detail="Widget file is missing")
    return FileResponse(
        path=str(WIDGET_JS_PATH),
        media_type="application/javascript; charset=utf-8",
        filename="mosobr-widget.js",
    )


@app.get("/api/logs/list")
def list_logs(_access: None = Depends(require_logs_access)) -> dict:
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
def download_logs(_access: None = Depends(require_logs_access)) -> FileResponse:
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
