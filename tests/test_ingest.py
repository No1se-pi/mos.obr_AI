from app.db.session import SessionLocal
from app.ingest.ingest_pipeline import run_ingest
from app.logger import setup_logger

setup_logger()


def main() -> None:
    db = SessionLocal()
    try:
        run_ingest(db)
        print("Ingest завершён успешно")
    finally:
        db.close()


if __name__ == "__main__":
    main()