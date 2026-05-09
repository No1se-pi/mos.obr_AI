from typing import Any

from sqlalchemy import JSON, Text, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

from app.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)


def create_tables(engine) -> None:
    logger.info("Создание таблиц в БД...")
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы успешно созданы")


def add_document(
    db: Session,
    doc_type: str,
    title: str,
    content: str,
    metadata_json: dict[str, Any],
    embedding: list[float],
) -> Document:
    document = Document(
        doc_type=doc_type,
        title=title,
        content=content,
        metadata_json=metadata_json,
        embedding_json=embedding,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document