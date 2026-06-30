import os
import time

from sqlalchemy import func, select, text

import app.db.chat_models  # noqa: F401 - registers chat tables in Base.metadata
from app.config import get_settings
from app.db.chat_models import ensure_chat_session_runtime_schema
from app.db.repository import Document, create_tables
from app.db.session import SessionLocal, engine
from app.ingest.ingest_pipeline import run_ingest
from app.ingest.source_fingerprint import DATA_FINGERPRINT_METADATA_KEY, current_data_fingerprint
from app.interfaces.cli import run_cli_chat
from app.interfaces.telegram_bot import main as run_telegram_bot
from app.logger import get_logger, setup_logger


logger = get_logger(__name__)


def wait_for_database() -> None:
    attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "60"))
    delay = float(os.getenv("DB_WAIT_DELAY", "2"))

    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is ready")
            return
        except Exception as exc:
            logger.warning("Database is not ready yet (%s/%s): %s", attempt, attempts, exc)
            time.sleep(delay)

    raise RuntimeError("Database did not become ready in time")


def document_count() -> int:
    db = SessionLocal()
    try:
        return int(db.execute(select(func.count(Document.id))).scalar_one())
    finally:
        db.close()


def document_type_count(doc_type: str) -> int:
    db = SessionLocal()
    try:
        stmt = select(func.count(Document.id)).where(Document.doc_type == doc_type)
        return int(db.execute(stmt).scalar_one())
    finally:
        db.close()


def document_source_count(source_type: str) -> int:
    db = SessionLocal()
    try:
        stmt = select(func.count(Document.id)).where(
            Document.metadata_json["source_type"].as_string() == source_type
        )
        return int(db.execute(stmt).scalar_one())
    finally:
        db.close()


def document_fingerprint_count(data_fingerprint: str) -> int:
    db = SessionLocal()
    try:
        stmt = select(func.count(Document.id)).where(
            Document.metadata_json[DATA_FINGERPRINT_METADATA_KEY].as_string() == data_fingerprint
        )
        return int(db.execute(stmt).scalar_one())
    finally:
        db.close()


def maybe_run_ingest() -> None:
    mode = os.getenv("BOOTSTRAP_INGEST", "auto").strip().lower()
    if mode in {"0", "false", "no", "off", "never"}:
        logger.info("Skipping ingest because BOOTSTRAP_INGEST=%s", mode)
        return

    # Auto mode avoids rebuilding embeddings on every container restart.
    should_ingest = mode in {"1", "true", "yes", "on", "always"}
    if mode == "auto":
        total_documents = document_count()
        faq_documents = document_type_count("faq")
        weeek_documents = document_source_count("weeek")
        data_fingerprint = current_data_fingerprint(get_settings())
        matching_fingerprint_documents = document_fingerprint_count(data_fingerprint)
        should_ingest = (
            total_documents == 0
            or faq_documents == 0
            or weeek_documents == 0
            or matching_fingerprint_documents != total_documents
        )
        if total_documents > 0 and faq_documents == 0:
            logger.warning("FAQ documents are missing; auto ingest will rebuild documents")
        if total_documents > 0 and weeek_documents == 0:
            logger.warning("Weeek documents are missing; auto ingest will rebuild documents")
        if total_documents > 0 and matching_fingerprint_documents != total_documents:
            logger.warning(
                "Data files changed or documents were built before fingerprinting; auto ingest will rebuild documents "
                "(matching fingerprint documents: %s/%s)",
                matching_fingerprint_documents,
                total_documents,
            )

    if not should_ingest:
        logger.info("Skipping ingest: documents already exist")
        return

    db = SessionLocal()
    try:
        logger.info("Starting ingest")
        run_ingest(db)
    finally:
        db.close()


def main() -> None:
    setup_logger()
    wait_for_database()
    create_tables(engine)
    ensure_chat_session_runtime_schema(engine)
    maybe_run_ingest()

    entrypoint = os.getenv("APP_ENTRYPOINT", "telegram").strip().lower()
    if entrypoint == "cli":
        run_cli_chat()
        return

    run_telegram_bot()


if __name__ == "__main__":
    main()
