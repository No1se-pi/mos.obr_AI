from app.db.session import SessionLocal
from app.logger import setup_logger
from app.services.chat_service import ChatService

setup_logger()


def main() -> None:
    db = SessionLocal()
    try:
        service = ChatService()

        user_id = "demo_user"
        session_id = None

        queries = [
            "Хочу в айти, но не знаю что выбрать",
            "Не хочу только сидеть в коде",
            "Мне скорее ближе что-то с техникой и железом",
            "Что тогда посмотреть из колледжей?",
        ]

        for query in queries:
            print("=" * 80)
            print("Вопрос:", query)
            print()

            result = service.ask(
                db=db,
                user_id=user_id,
                user_query=query,
                session_id=session_id,
                top_k=5,
            )

            session_id = result["session_id"]

            print("SESSION_ID:", session_id)
            print("MODE:", result["dialog_mode"])
            print("Ответ:")
            print(result["answer"])
            print()

    finally:
        db.close()


if __name__ == "__main__":
    main()