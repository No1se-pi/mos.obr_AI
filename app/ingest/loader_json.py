import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def load_json_data() -> list[dict[str, Any]]:
    data_path = Path(settings.data_path)

    if not data_path.exists():
        raise FileNotFoundError(f"Файл не найден: {data_path}")

    logger.info(f"Загрузка JSON из {data_path}")

    with data_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Ожидался список объектов в JSON")

    logger.info(f"Успешно загружено записей: {len(data)}")
    return data