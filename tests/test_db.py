from sqlalchemy import text

from app.db.session import engine
from app.logger import setup_logger, get_logger

setup_logger()
logger = get_logger(__name__)


def main():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("DB OK:", result.scalar())
            logger.info("Подключение к БД успешно")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")


if __name__ == "__main__":
    main()