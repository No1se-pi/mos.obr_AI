import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.chat_models import ChatMessage, ChatSession
from app.logger import get_logger

logger = get_logger(__name__)


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