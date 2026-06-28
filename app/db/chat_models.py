from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, inspect, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.repository import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Новый диалог", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_db_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


def ensure_chat_session_runtime_schema(engine) -> None:
    """
    create_all() does not alter existing local databases. This keeps older
    chat_sessions tables compatible after adding route-state metadata.
    """
    inspector = inspect(engine)
    if not inspector.has_table("chat_sessions"):
        return

    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    if "metadata_json" in columns:
        return

    if engine.dialect.name == "postgresql":
        ddl = "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS metadata_json JSON DEFAULT '{}' NOT NULL"
    else:
        ddl = "ALTER TABLE chat_sessions ADD COLUMN metadata_json JSON DEFAULT '{}'"

    with engine.begin() as conn:
        conn.execute(text(ddl))
