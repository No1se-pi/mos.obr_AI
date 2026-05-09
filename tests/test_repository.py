from app.db.chat_models import ChatMessage, ChatSession
from app.db.repository import create_tables
from app.db.session import engine
from app.logger import setup_logger

setup_logger()


def main() -> None:
    _ = ChatSession
    _ = ChatMessage

    create_tables(engine)
    print("Таблицы созданы")


if __name__ == "__main__":
    main()