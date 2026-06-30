from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.ingest.document_builder import collect_domain_tags
from app.logger import get_logger

logger = get_logger(__name__)


INDUSTRY_TITLES: dict[str, str] = {
    "it": "IT и цифровые технологии",
    "design": "Дизайн и креативные индустрии",
    "music": "Музыка и сценическое искусство",
    "law": "Право и безопасность",
    "finance": "Финансы и экономика",
    "tourism": "Туризм, сервис и гостеприимство",
    "transport": "Транспорт и логистика",
    "production": "Промышленность",
    "medicine": "Медицина и здоровье",
    "construction": "Строительство, архитектура и инженерия",
    "media": "Медиа, кино и анимация",
}


def normalize_key(text: str) -> str:
    text = text.lower().replace("ё", "е").strip()
    text = re.sub(r"[^\w\s.-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = str(value).strip()
        key = normalize_key(value)
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def medicine_college_entry_priority(entry: dict[str, Any]) -> tuple[int, int, str]:
    college = normalize_key(str(entry.get("college", "")))
    specialty = normalize_key(str(entry.get("specialty", "")))
    is_med_college = 0 if "медицинский колледж" in college or "училище сестер" in college else 1
    is_med_specialty = 0 if any(
        marker in specialty
        for marker in ["сестрин", "стомат", "медицин", "фармац", "лабораторная диагностика"]
    ) else 1
    return (is_med_college, is_med_specialty, college)


def medicine_profession_priority(profession: str) -> tuple[int, str]:
    normalized = normalize_key(profession)
    is_core = 0 if any(
        marker in normalized
        for marker in ["медицин", "фельдшер", "фармацевт", "зубной", "оптометрист", "оптик"]
    ) else 1
    return (is_core, normalized)


def build_reference_indexes(colleges: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    profession_index: dict[str, dict[str, Any]] = {}
    industry_index: dict[str, dict[str, Any]] = {
        domain: {
            "title": title,
            "professions": [],
            "specialties": [],
            "college_specialties": [],
        }
        for domain, title in INDUSTRY_TITLES.items()
    }

    for college in colleges:
        college_name = str(college.get("name", "")).strip()
        website = str(college.get("website", "")).strip()
        atlas_url = str(college.get("atlas_url", "")).strip()
        addresses = [str(item).strip() for item in college.get("addresses", []) if str(item).strip()]
        contacts = [str(item).strip() for item in college.get("contacts", []) if str(item).strip()]

        for specialty in college.get("specialties", []):
            specialty_name = str(specialty.get("name", "")).strip()
            specialty_url = str(specialty.get("atlas_url", "")).strip()
            professions = unique_keep_order([str(p) for p in specialty.get("professions", [])])
            domain_tags = collect_domain_tags(specialty_name, " ".join(professions))

            base_entry = {
                "college": college_name,
                "specialty": specialty_name,
                "professions": professions,
                "website": website,
                "atlas_url": atlas_url,
                "specialty_url": specialty_url,
                "contacts": contacts,
                "addresses": addresses,
                "industry_tags": domain_tags,
            }

            # Индекс профессий нужен для точных ответов без случайного RAG-попадания.
            for profession in professions:
                key = normalize_key(profession)
                if not key:
                    continue
                bucket = profession_index.setdefault(
                    key,
                    {
                        "display_name": profession,
                        "colleges": [],
                    },
                )
                bucket["colleges"].append({**base_entry, "matched_profession": profession})

            # Индекс отраслей показывает, какие профессии и колледжи есть внутри направления.
            for domain in domain_tags:
                industry = industry_index.setdefault(
                    domain,
                    {
                        "title": INDUSTRY_TITLES.get(domain, domain),
                        "professions": [],
                        "specialties": [],
                        "college_specialties": [],
                    },
                )
                industry["professions"].extend(professions)
                industry["specialties"].append(specialty_name)
                industry["college_specialties"].append(base_entry)

    for bucket in profession_index.values():
        bucket["colleges"] = dedupe_college_entries(bucket["colleges"])

    for industry in industry_index.values():
        industry["professions"] = unique_keep_order(industry["professions"])
        industry["specialties"] = unique_keep_order(industry["specialties"])
        industry["college_specialties"] = dedupe_college_entries(industry["college_specialties"])

    if "medicine" in industry_index:
        industry_index["medicine"]["professions"].sort(key=medicine_profession_priority)
        industry_index["medicine"]["college_specialties"].sort(key=medicine_college_entry_priority)

    profession_payload = {
        "version": 1,
        "source": "colleges.json",
        "total_professions": len(profession_index),
        "professions": dict(sorted(profession_index.items())),
    }
    industry_payload = {
        "version": 1,
        "source": "colleges.json",
        "industries": industry_index,
    }
    return profession_payload, industry_payload


def dedupe_college_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for entry in entries:
        key = (normalize_key(str(entry.get("college", ""))), normalize_key(str(entry.get("specialty", ""))))
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def write_reference_indexes(colleges: list[dict[str, Any]], data_dir: Path) -> None:
    profession_payload, industry_payload = build_reference_indexes(colleges)
    data_dir.mkdir(parents=True, exist_ok=True)

    profession_path = data_dir / "profession_colleges.json"
    industry_path = data_dir / "industry_professions.json"

    profession_path.write_text(
        json.dumps(profession_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    industry_path.write_text(
        json.dumps(industry_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Reference indexes updated: %s professions, %s industries",
        profession_payload["total_professions"],
        len(industry_payload["industries"]),
    )


def main() -> None:
    data_dir = Path("data")
    colleges_path = data_dir / "colleges.json"
    colleges = json.loads(colleges_path.read_text(encoding="utf-8"))
    if not isinstance(colleges, list):
        raise ValueError("colleges.json must contain a list")
    write_reference_indexes(colleges, data_dir)


if __name__ == "__main__":
    main()
