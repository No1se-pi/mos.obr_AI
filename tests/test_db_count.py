from sqlalchemy import func, select

from app.db.repository import Document
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(Document))
        print("Количество документов в БД:", count)
    finally:
        db.close()


if __name__ == "__main__":
    main()