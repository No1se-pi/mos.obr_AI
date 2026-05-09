from typing import Any

from app.logger import get_logger

logger = get_logger(__name__)


def clean_text(text: str) -> str:
    return text.strip()


def normalize_college(college: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": clean_text(college.get("name", "")),
        "aliases": [clean_text(a) for a in college.get("aliases", [])],
        "specialties": [
            {
                "name": clean_text(spec.get("name", "")),
                "professions": [
                    clean_text(p) for p in spec.get("professions", [])
                ],
            }
            for spec in college.get("specialties", [])
        ],
        "addresses": [clean_text(a) for a in college.get("addresses", [])],
        "contacts": [clean_text(c) for c in college.get("contacts", [])],
        "website": clean_text(college.get("website", "")),
    }


def normalize_data(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logger.info("Нормализация данных...")

    normalized = [normalize_college(college) for college in data]

    logger.info(f"Нормализовано записей: {len(normalized)}")
    return normalized