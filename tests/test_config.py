from app.config import get_settings
from app.logger import setup_logger, get_logger


def main() -> None:
    setup_logger()
    logger = get_logger(__name__)

    settings = get_settings()

    logger.info("Старт теста конфига")

    print("APP_NAME:", settings.app_name)
    print("OLLAMA_MODEL:", settings.ollama_model)
    print("EMBEDDING_MODEL:", settings.embedding_model)
    print("POSTGRES_URL:", settings.postgres_url)
    print("DATA_PATH:", settings.data_path)
    print("TOP_K:", settings.top_k)
    print("TOP_K type:", type(settings.top_k))

    logger.info("Тест завершён")


if __name__ == "__main__":
    main()