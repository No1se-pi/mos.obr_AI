import os
import time

from sqlalchemy import func, select, text

import app.db.chat_models  # noqa: F401 - registers chat tables in Base.metadata
from app.db.repository import Document, create_tables
from app.db.session import SessionLocal, engine
from app.ingest.ingest_pipeline import run_ingest
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


def maybe_run_ingest() -> None:
    mode = os.getenv("BOOTSTRAP_INGEST", "auto").strip().lower()
    if mode in {"0", "false", "no", "off", "never"}:
        logger.info("Skipping ingest because BOOTSTRAP_INGEST=%s", mode)
        return

    should_ingest = mode in {"1", "true", "yes", "on", "always"}
    if mode == "auto":
        should_ingest = document_count() == 0

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
    maybe_run_ingest()

    entrypoint = os.getenv("APP_ENTRYPOINT", "telegram").strip().lower()
    if entrypoint == "cli":
        run_cli_chat()
        return

    run_telegram_bot()


if __name__ == "__main__":
    main()
