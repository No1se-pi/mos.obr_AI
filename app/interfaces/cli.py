from app.core.singletons import get_chat_service
from app.db.session import SessionLocal
from app.logger import get_logger

logger = get_logger(__name__)


EXIT_COMMANDS = {"exit", "quit", "q", "выход", "стоп"}


def run_cli_chat() -> None:
    print("=" * 80)
    print("Локальный AI-помощник по профориентации")
    print("Напиши вопрос. Для выхода: exit / quit / выход")
    print("=" * 80)
    print()

    user_id = input("Введите user_id (например, your_name): ").strip() or "local_user"
    session_id: str | None = None

    chat_service = get_chat_service()

    db = SessionLocal()
    try:
        while True:
            user_query = input("\nТы: ").strip()

            if not user_query:
                continue

            if user_query.lower() in EXIT_COMMANDS:
                print("\nПока 👋")
                break

            result = chat_service.ask(
                db=db,
                user_id=user_id,
                user_query=user_query,
                session_id=session_id,
                top_k=5,
            )

            session_id = result["session_id"]

            print(f"\n[session_id: {session_id}]")
            print(f"[mode: {result.get('dialog_mode', 'unknown')}]")
            print(f"\nАссистент: {result['answer']}")
    finally:
        db.close()
        logger.info("CLI чат завершён")