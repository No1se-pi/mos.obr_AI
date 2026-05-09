from app.db.session import SessionLocal
from app.logger import setup_logger
from app.services.session_service import SessionService

setup_logger()


def main() -> None:
    db = SessionLocal()
    try:
        service = SessionService()

        session = service.get_or_create_session(
            db=db,
            user_id="test_user_1",
            title="Тестовый диалог",
        )

        print("SESSION_ID:", session.session_id)
        print("TITLE:", session.title)

        service.add_message(db, session, "user", "Привет, хочу в айти")
        service.add_message(db, session, "assistant", "Окей, давай подберём варианты")
        service.add_message(db, session, "user", "Но не хочу чисто программировать")

        messages = service.get_recent_messages(db, session, limit=10)

        print("\nИстория сообщений:\n")
        for msg in messages:
            print(f"[{msg.role}] {msg.content}")

    finally:
        db.close()


if __name__ == "__main__":
    main()