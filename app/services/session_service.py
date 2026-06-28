import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chat_models import ChatMessage, ChatSession
from app.logger import get_logger

logger = get_logger(__name__)


DEFAULT_ROUTE_STATE: dict[str, Any] = {
    "user_type": None,
    "current_route": None,
    "route_step": None,
    "last_college": None,
    "last_profession": None,
    "last_industry": None,
    "last_specialty": None,
    "last_results": [],
    "last_answer": None,
    "tone_mode": None,
}


class SessionService:
    def get_or_create_session(
        self,
        db: Session,
        user_id: str,
        session_id: str | None = None,
        title: str = "Новый диалог",
    ) -> ChatSession:
        if session_id:
            existing_session = db.scalar(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            if existing_session:
                return existing_session

        new_session = ChatSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            metadata_json=DEFAULT_ROUTE_STATE.copy(),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        logger.info(f"Создана новая сессия: {new_session.session_id}")
        return new_session

    def add_message(
        self,
        db: Session,
        session: ChatSession,
        role: str,
        content: str,
    ) -> ChatMessage:
        message = ChatMessage(
            session_db_id=session.id,
            role=role,
            content=content,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        return message

    def get_recent_messages(
        self,
        db: Session,
        session: ChatSession,
        limit: int = 10,
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_db_id == session.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )

        messages = list(db.scalars(stmt).all())
        messages.reverse()
        return messages

    def get_route_state(self, session: ChatSession) -> dict[str, Any]:
        raw = session.metadata_json or {}
        if not isinstance(raw, dict):
            raw = {}
        state = DEFAULT_ROUTE_STATE.copy()
        state.update(raw)
        if state.get("user_type") in {"parent", "applicant"} and not state.get("tone_mode"):
            state["tone_mode"] = state["user_type"]
        return state

    def update_route_state(
        self,
        db: Session,
        session: ChatSession,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.get_route_state(session)
        state.update(updates)
        session.metadata_json = state
        db.add(session)
        db.commit()
        db.refresh(session)
        return self.get_route_state(session)

    def reset_route_state(self, db: Session, session: ChatSession) -> dict[str, Any]:
        session.metadata_json = DEFAULT_ROUTE_STATE.copy()
        db.add(session)
        db.commit()
        db.refresh(session)
        return self.get_route_state(session)
