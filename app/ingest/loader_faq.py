from pathlib import Path
from typing import Any

from app.logger import get_logger

logger = get_logger(__name__)


def load_faq_json(data_path: str) -> list[dict[str, Any]]:
    path = Path(data_path)

    if not path.exists():
        raise FileNotFoundError(f"FAQ файл не найден: {data_path}")

    logger.info(f"Загрузка FAQ JSON из {data_path}")

    import json

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("FAQ JSON должен быть списком объектов")

    logger.info(f"Успешно загружено FAQ записей: {len(data)}")
    return data