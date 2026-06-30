from pathlib import Path
from typing import Any

from app.logger import get_logger

logger = get_logger(__name__)


def load_weeek_knowledge_json(data_path: str) -> list[dict[str, Any]]:
    path = Path(data_path)

    if not path.exists():
        logger.info("Weeek knowledge file is missing, skipping: %s", data_path)
        return []

    logger.info("Загрузка Weeek knowledge JSON из %s", data_path)

    import json

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Weeek knowledge JSON должен быть списком объектов")

    documents = [item for item in data if isinstance(item, dict)]
    logger.info("Успешно загружено Weeek knowledge записей: %s", len(documents))
    return documents
