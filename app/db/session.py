from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)


settings = get_settings()

engine = create_engine(
    settings.postgres_url,
    echo=False,  # если поставить True — будет лог SQL-запросов
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()