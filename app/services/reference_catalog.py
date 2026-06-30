from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.ingest.reference_indexes import normalize_key
from app.logger import get_logger

logger = get_logger(__name__)


STOPWORDS = {
    "где",
    "куда",
    "какие",
    "какой",
    "какая",
    "колледж",
    "колледжи",
    "учиться",
    "учат",
    "посоветуй",
    "подбери",
    "поступить",
    "поступать",
    "профессия",
    "профессии",
    "специальность",
    "специальности",
    "хочу",
    "стать",
    "для",
    "про",
}

INDUSTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "it": (
        "it",
        "айти",
        "программирование",
        "разработка",
        "цифровые технологии",
        "информационные технологии",
        "нейросети",
        "искусственный интеллект",
        "кибербезопасность",
        "информационная безопасность",
        "защита информации",
        "хакинг",
        "хакер",
        "пентест",
        "сети",
        "администрирование",
    ),
    "design": ("дизайн", "дизайнер", "креатив", "креативная индустрия", "рисование", "арт", "фотография"),
    "music": ("музыка", "музык", "джаз", "вокал", "сцена"),
    "law": ("право", "юрист", "юриспруденция", "полиция", "правоохранительная деятельность"),
    "finance": ("финансы", "экономика", "банк", "бухгалтер", "деньги"),
    "tourism": ("туризм", "гостеприимство", "сервис", "отель"),
    "transport": ("транспорт", "логистика", "перевозки", "метро", "машинист"),
    "medicine": ("медицина", "медицин", "здоровье", "здравоохранение", "медик", "сестринское"),
    "production": (
        "промышленность",
        "производство",
        "промышленное оборудование",
        "станки",
        "станок",
        "робототехника",
        "мехатроника",
        "машиностроение",
        "сварка",
        "сварщик",
        "бпла",
        "аддитивные технологии",
    ),
    "construction": (
        "строительство",
        "архитектура",
        "инженерия",
        "инженер",
    ),
    "media": ("медиа", "кино", "анимация", "телевидение", "звук"),
}

RU_SUFFIXES = (
    "иями",
    "ями",
    "ами",
    "ого",
    "ему",
    "ому",
    "ыми",
    "ими",
    "ая",
    "яя",
    "ое",
    "ее",
    "ые",
    "ие",
    "ый",
    "ий",
    "ой",
    "а",
    "я",
    "ы",
    "и",
    "у",
    "ю",
    "ом",
    "ем",
    "ах",
    "ях",
)


@dataclass(slots=True)
class ProfessionMatch:
    key: str
    display_name: str
    colleges: list[dict[str, Any]]
    score: float


@dataclass(slots=True)
class IndustryMatch:
    key: str
    title: str
    professions: list[str]
    college_specialties: list[dict[str, Any]]
    score: float


def data_dir_from_settings() -> Path:
    try:
        return Path(get_settings().data_path).parent
    except Exception:
        return Path("data")


def token_stem(token: str) -> str:
    token = normalize_key(token)
    for suffix in RU_SUFFIXES:
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def meaningful_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[а-яa-z0-9.-]+", normalize_key(text)):
        if token in STOPWORDS or len(token) < 3:
            continue
        tokens.add(token_stem(token))
    return tokens


class ReferenceCatalog:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or data_dir_from_settings()
        self._profession_data: dict[str, Any] | None = None
        self._industry_data: dict[str, Any] | None = None

    def profession_data(self) -> dict[str, Any]:
        if self._profession_data is None:
            self._profession_data = self._load_json("profession_colleges.json")
        return self._profession_data

    def industry_data(self) -> dict[str, Any]:
        if self._industry_data is None:
            self._industry_data = self._load_json("industry_professions.json")
        return self._industry_data

    def _load_json(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("Reference catalog file is missing: %s", path)
            return {}
        except Exception as exc:
            logger.warning("Reference catalog file cannot be loaded %s: %s", path, exc)
            return {}

    def match_professions(self, query: str, limit: int = 3) -> list[ProfessionMatch]:
        professions = self.profession_data().get("professions", {})
        if not isinstance(professions, dict):
            return []

        query_norm = normalize_key(query)
        query_tokens = meaningful_tokens(query_norm)
        matches: list[ProfessionMatch] = []

        for key, payload in professions.items():
            display_name = str(payload.get("display_name") or key)
            key_norm = normalize_key(key)
            key_tokens = meaningful_tokens(key_norm)
            if not key_tokens:
                continue

            score = 0.0
            if key_norm and key_norm in query_norm:
                score += 4.0 + min(len(key_norm), 40) / 40

            overlap = query_tokens.intersection(key_tokens)
            if overlap:
                score += len(overlap) / max(len(key_tokens), 1) * 3.0

            # Для коротких профессий вроде "программист" substring важнее embeddings.
            if any(token and token in query_norm for token in key_tokens):
                score += 1.2

            if score < 1.6:
                continue

            colleges = payload.get("colleges", [])
            if isinstance(colleges, list) and colleges:
                matches.append(ProfessionMatch(key_norm, display_name, colleges, score))

        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:limit]

    def match_industry(self, query: str) -> IndustryMatch | None:
        industries = self.industry_data().get("industries", {})
        if not isinstance(industries, dict):
            return None

        query_norm = normalize_key(query)
        query_tokens = meaningful_tokens(query_norm)
        best: IndustryMatch | None = None

        for key, aliases in INDUSTRY_ALIASES.items():
            payload = industries.get(key)
            if not isinstance(payload, dict):
                continue

            score = 0.0
            for alias in aliases:
                alias_norm = normalize_key(alias)
                alias_tokens = meaningful_tokens(alias_norm)
                if alias_norm and alias_norm in query_norm:
                    score += 4.0
                score += len(query_tokens.intersection(alias_tokens)) * 1.5

            if score <= 0:
                continue

            candidate = IndustryMatch(
                key=key,
                title=str(payload.get("title") or key),
                professions=[str(item) for item in payload.get("professions", []) if str(item).strip()],
                college_specialties=[
                    item for item in payload.get("college_specialties", []) if isinstance(item, dict)
                ],
                score=score,
            )
            if best is None or candidate.score > best.score:
                best = candidate

        return best
