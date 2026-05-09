import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import Document
from app.logger import get_logger
from app.rag.embedder import Embedder

logger = get_logger(__name__)
settings = get_settings()


STOPWORDS = {
    "где",
    "на",
    "в",
    "и",
    "или",
    "по",
    "для",
    "как",
    "что",
    "к",
    "из",
    "у",
    "о",
    "об",
    "от",
    "до",
    "ли",
    "а",
    "но",
    "же",
    "бы",
    "это",
    "то",
    "я",
    "мы",
    "ты",
    "он",
    "она",
    "они",
    "учиться",
    "какие",
    "есть",
    "короче",
    "скажем",
    "так",
    "тогда",
    "вообще",
    "просто",
    "мне",
    "мой",
    "моя",
    "моё",
    "мой",
    "хочу",
    "стать",
    "посоветуй",
    "лучше",
    "куда",
    "стоит",
    "расскажи",
    "подробнее",
}

FAQ_HINTS = {
    "документы",
    "документ",
    "поступить",
    "поступление",
    "зачисление",
    "заявление",
    "mos.ru",
    "мос.ру",
    "сроки",
    "льготы",
    "овз",
    "инвалид",
    "отсрочка",
    "армия",
    "вуз",
    "егэ",
    "огэ",
    "гвэ",
    "гия",
    "стипендия",
    "общежитие",
    "питание",
    "проезд",
    "иностран",
    "апостиль",
    "нострификация",
    "практика",
    "трудоустройство",
    "целевое",
    "вступительные",
    "испытания",
    "экзамены",
    "бюджет",
    "конкурс",
}

CAREER_HINTS = {
    "хочу",
    "стать",
    "кем",
    "профессия",
    "специальность",
    "направление",
    "куда",
    "посоветуй",
    "лучше",
    "обучение",
    "фотограф",
    "дизайнер",
    "программист",
    "разработчик",
    "инженер",
    "безопасность",
    "реклама",
    "ml",
    "айти",
    "it",
}

QUERY_DOMAIN_RULES: dict[str, set[str]] = {
    "it": {
        "программист",
        "программирование",
        "разработка",
        "разработчик",
        "веб",
        "айти",
        "it",
        "кибербез",
        "кибербезопасность",
        "безопасность",
        "администратор",
        "devops",
        "frontend",
        "backend",
        "ml",
        "сети",
        "серверы",
        "инженер",
        "алгоритмы",
        "данные",
    },
    "design": {
        "графический",
        "дизайнер",
        "дизайн",
        "иллюстратор",
        "графдизайн",
        "визуал",
    },
    "photo": {
        "фото",
        "фотограф",
        "фотодизайнер",
        "видеограф",
        "фотосъемка",
        "фотография",
    },
    "advertising": {
        "реклама",
        "маркетинг",
        "бренд",
        "продвижение",
        "рекламный",
    },
    "music": {
        "музыка",
        "музыкант",
        "вокал",
        "артист",
    },
    "law": {
        "юрист",
        "юриспруденция",
        "право",
        "полицейский",
    },
    "finance": {
        "финансы",
        "бухгалтер",
        "экономика",
        "банковское",
    },
    "tourism": {
        "туризм",
        "гостеприимство",
        "отель",
    },
    "transport": {
        "транспорт",
        "логистика",
        "машинист",
        "метро",
    },
    "construction": {
        "строительство",
        "архитектура",
        "bim",
        "сварщик",
        "сантехник",
        "электромонтажник",
    },
    "media": {
        "анимация",
        "кино",
        "актер",
        "звукорежиссер",
    },
    "pedagogy": {
        "педагог",
        "педагогика",
        "учитель",
        "преподаватель",
        "вожатый",
        "мгпу",
        "ушинского",
        "испо",
        "образование",
        "мпк",
    },
    "art": {
        "рисовать",
        "рисую",
        "картины",
        "живопись",
        "художник",
        "арт",
        "искусство",
        "иллюстрация",
    },
    "fashion": {
        "мода",
        "одежда",
        "костюм",
        "костюмы",
        "художник",
        "швейный",
        "текстиль",
    },
    "cooking": {
        "повар",
        "кондитер",
        "готовить",
        "кулинария",
    },
}

SPECIALTY_ANCHORS: dict[str, dict[str, list[str]]] = {
    "cybersecurity": {
        "query_aliases": [
            "белый хакер",
            "этичный хакер",
            "кибербез",
            "кибербезопасность",
            "информационная безопасность",
            "инженер по информационной безопасности",
            "безопасность систем",
            "защита систем",
            "защита информации",
            "поиск уязвимостей",
            "пентест",
            "пентестер",
        ],
        "specialty_targets": [
            "обеспечение информационной безопасности автоматизированных систем",
            "обеспечение информационной безопасности телекоммуникационных систем",
        ],
    },
    "software": {
        "query_aliases": [
            "программист",
            "разработчик",
            "код",
            "кодить",
            "разработка",
            "веб",
            "веб-разработка",
            "backend",
            "frontend",
            "разработка по",
            "ml инженер",
            "машинное обучение",
            "ml",
        ],
        "specialty_targets": [
            "разработка и управление программным обеспечением",
            "веб-разработка",
            "разработка компьютерных игр",
            "интеллектуальные интегрированные системы",
        ],
    },
    "sysadmin": {
        "query_aliases": [
            "сети",
            "серверы",
            "админ",
            "системный администратор",
            "системное администрирование",
            "сетевик",
            "инфраструктура",
            "железо",
            "техника",
        ],
        "specialty_targets": [
            "сетевое и системное администрирование",
            "компьютерные системы и комплексы",
            "интеллектуальные интегрированные системы",
            "инфокоммуникационные сети и системы связи",
        ],
    },
    "graphic_design": {
        "query_aliases": [
            "графдизайн",
            "графический дизайнер",
            "графика",
            "визуал",
            "иллюстрация",
            "дизайн",
            "дизайнер",
        ],
        "specialty_targets": [
            "графический дизайнер",
            "дизайн",
            "реклама",
            "анимация и анимационное кино",
        ],
    },
    "photo": {
        "query_aliases": [
            "фото",
            "фотограф",
            "фотография",
            "видеограф",
            "фотодизайнер",
        ],
        "specialty_targets": [
            "техника и искусство фотографии",
            "графический дизайнер",
        ],
    },
    "advertising": {
        "query_aliases": [
            "реклама",
            "рекламщик",
            "маркетинг",
            "продвижение",
        ],
        "specialty_targets": [
            "реклама",
            "графический дизайнер",
            "дизайн",
        ],
    },
    "law": {
        "query_aliases": [
            "юрист",
            "право",
            "суд",
            "правоохранительная деятельность",
            "полицейский",
        ],
        "specialty_targets": [
            "юриспруденция",
            "правоохранительная деятельность",
        ],
    },
    "finance": {
        "query_aliases": [
            "финансы",
            "бухгалтер",
            "банк",
            "банковское дело",
            "экономика",
        ],
        "specialty_targets": [
            "финансы",
            "банковское дело",
            "экономика и бухгалтерский учет",
        ],
    },
    "pedagogy": {
        "query_aliases": [
            "педагогический колледж",
            "педагог",
            "педагогика",
            "педагогикой",
            "педагогику",
            "учитель",
            "преподаватель",
            "мгпу",
            "ушинского",
            "испо ушинского",
        ],
        "specialty_targets": [
            "коррекционная педагогика в начальном образовании",
            "преподавание в начальных классах",
            "дошкольное образование",
            "физическая культура",
            "спорт",
        ],
    },
    "painting": {
        "query_aliases": [
            "рисовать",
            "картины",
            "живопись",
            "художник",
            "арт",
        ],
        "specialty_targets": [
            "живопись",
            "художник",
            "дизайн",
            "графический дизайнер",
        ],
    },
    "fashion": {
        "query_aliases": [
            "мода",
            "одежда",
            "художник по костюму",
            "костюм",
            "костюмы",
            "дизайнер одежды",
        ],
        "specialty_targets": [
            "художник по костюму",
            "художественное оформление изделий текстильной и легкой промышленности",
            "дизайн",
        ],
    },
}

PREFERRED_COLLEGE_RULES: dict[str, set[str]] = {
    "it": {
        "ит.москва",
        "колледж автоматизации и информационных технологий № 20",
        "колледж связи № 54 имени п.м. вострухина",
    },
    "design": {
        "26 кадр",
        "колледж автоматизации и информационных технологий № 20",
    },
    "photo": {
        "26 кадр",
        "колледж автоматизации и информационных технологий № 20",
    },
    "advertising": {
        "26 кадр",
    },
    "pedagogy": {
        "мгпу",
        "институт среднего профессионального образования имени к. д. ушинского",
        "московский педагогический колледж",
    },
    "art": {
        "первый московский образовательный комплекс",
        "московский техникум креативных индустрий им. л.б. красина",
        "колледж декоративно-прикладного искусства имени карла фаберже",
        "26 кадр",
    },
    "fashion": {
        "колледж декоративно-прикладного искусства имени карла фаберже",
        "колледж ргу им. а.н. косыгина",
        "26 кадр",
    },
}

UNIVERSITY_MARKERS = {
    "университет",
    "институт",
    "академия",
}


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def normalize_token(token: str) -> str:
    token = token.lower().strip()

    replacements = {
        "программиста": "программист",
        "программистом": "программист",
        "программисты": "программист",
        "программирования": "программирование",
        "программированию": "программирование",
        "разработчика": "разработчик",
        "разработчиком": "разработчик",
        "разработки": "разработка",
        "разработку": "разработка",
        "дизайнера": "дизайнер",
        "дизайнеру": "дизайнер",
        "дизайнером": "дизайнер",
        "графического": "графический",
        "графическому": "графический",
        "кибербезопасности": "кибербезопасность",
        "безопасности": "безопасность",
        "инженером": "инженер",
        "инженера": "инженер",
        "систем": "система",
        "системы": "система",
        "серверов": "сервер",
        "сетей": "сеть",
        "сетями": "сеть",
        "хакером": "хакер",
        "хакера": "хакер",
        "фотографа": "фотограф",
        "фотографом": "фотограф",
        "фотографии": "фотография",
        "фотографиий": "фотография",
        "дизайну": "дизайн",
        "рекламе": "реклама",
        "инженером": "инженер",
        "инженеру": "инженер",
        "инженеры": "инженер",
        "учиться": "обучение",
        "педагогические": "педагогика",
        "педагогический": "педагогика",
        "педагогических": "педагогика",
        "учителя": "учитель",
        "учителем": "учитель",
        "рисую": "рисовать",
        "картину": "картины",
        "картина": "картины",
        "костюмам": "костюм",
        "костюмов": "костюм",
        "одежды": "одежда",
        "педагогикой": "педагогика",
        "педагогику": "педагогика",
        "педагогов": "педагог",
        "учителем": "учитель",
        "учителя": "учитель",
        "учителей": "учитель",
    }

    return replacements.get(token, token)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s№.-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"\w+", text.lower())
    normalized = [normalize_token(token) for token in raw_tokens]
    return [token for token in normalized if token and token not in STOPWORDS]


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def detect_query_domains(query: str) -> set[str]:
    query_tokens = token_set(query)
    domains: set[str] = set()

    for domain, keywords in QUERY_DOMAIN_RULES.items():
        if query_tokens.intersection(keywords):
            domains.add(domain)

    return domains


def is_faq_like_query(query: str) -> bool:
    query_tokens = token_set(query)
    if not query_tokens:
        return False

    faq_hits = len(query_tokens.intersection(FAQ_HINTS))
    career_hits = len(query_tokens.intersection(CAREER_HINTS))

    if faq_hits >= 2 and career_hits == 0:
        return True

    query_lower = normalize_text(query)
    direct_faq_markers = [
        "какие документы",
        "как поступить",
        "армия",
        "отсрочка",
        "забрать в армию",
        "овз",
        "инвалид",
        "питание",
        "общежитие",
        "стипендия",
        "mos.ru",
        "мос.ру",
    ]
    if any(marker in query_lower for marker in direct_faq_markers):
        return True

    return False


def get_anchor_matches(query: str) -> list[str]:
    query_lower = normalize_text(query)
    matched_groups: list[str] = []

    for anchor_name, anchor_data in SPECIALTY_ANCHORS.items():
        aliases = anchor_data["query_aliases"]
        if any(alias in query_lower for alias in aliases):
            matched_groups.append(anchor_name)

    return matched_groups


def keyword_score(query: str, doc: Document) -> float:
    query_tokens = token_set(query)

    title_tokens = token_set(doc.title)
    content_tokens = token_set(doc.content)

    specialty_name = str(doc.metadata_json.get("specialty_name", ""))
    specialty_tokens = token_set(specialty_name)

    college_name = str(doc.metadata_json.get("college_name", ""))
    college_tokens = token_set(college_name)

    profession_tokens: set[str] = set()
    for profession in doc.metadata_json.get("professions", []):
        profession_tokens.update(token_set(str(profession)))

    score = 0.0

    for token in query_tokens:
        if token in title_tokens:
            score += 0.30
        if token in specialty_tokens:
            score += 1.00
        if token in profession_tokens:
            score += 0.90
        if token in college_tokens:
            score += 0.45
        if token in content_tokens:
            score += 0.12

    return score


def domain_score(query: str, doc: Document) -> float:
    query_domains = detect_query_domains(query)
    if not query_domains:
        return 0.0

    doc_tags = set(doc.metadata_json.get("domain_tags", []))
    college_profile_scores = doc.metadata_json.get("college_profile_scores", {})

    score = 0.0

    for domain in query_domains:
        if domain in doc_tags:
            score += 0.75

        profile_value = float(college_profile_scores.get(domain, 0.0))
        score += min(profile_value * 0.12, 0.80)

    return score


def anchor_score(query: str, doc: Document) -> float:
    matched_anchors = get_anchor_matches(query)
    if not matched_anchors:
        return 0.0

    specialty_name = str(doc.metadata_json.get("specialty_name", "")).lower()
    title = doc.title.lower()
    content = doc.content.lower()

    score = 0.0

    for anchor_name in matched_anchors:
        targets = SPECIALTY_ANCHORS[anchor_name]["specialty_targets"]
        for target in targets:
            if target in specialty_name:
                score += 1.80
            elif target in title:
                score += 1.00
            elif target in content:
                score += 0.35

    return score


def specialty_priority_score(doc: Document, faq_like: bool) -> float:
    if faq_like:
        if doc.doc_type == "faq":
            return 0.60
        if doc.doc_type == "specialty":
            return -0.25
        return 0.0

    if doc.doc_type == "specialty":
        return 0.35
    if doc.doc_type == "faq":
        return -0.20
    return 0.05


def preferred_college_score(query: str, doc: Document) -> float:
    college_name = normalize_text(str(doc.metadata_json.get("college_name", "")))
    if not college_name:
        return 0.0

    query_domains = detect_query_domains(query)
    if not query_domains:
        return 0.0

    score = 0.0
    for domain in query_domains:
        preferred_names = PREFERRED_COLLEGE_RULES.get(domain, set())
        if any(preferred in college_name for preferred in preferred_names):
            score += 1.30
            if doc.doc_type == "specialty":
                score += 0.25

    return score


def university_penalty(doc: Document) -> float:
    college_name = normalize_text(str(doc.metadata_json.get("college_name", "")))
    title = normalize_text(doc.title)

    haystack = f"{college_name} {title}".strip()
    if any(marker in haystack for marker in UNIVERSITY_MARKERS):
        return -0.85

    return 0.0


def exact_college_match_score(query: str, doc: Document) -> float:
    query_lower = normalize_text(query)
    college_name = normalize_text(str(doc.metadata_json.get("college_name", "")))
    if not college_name:
        return 0.0

    compact_variants = {
        "каит 20": "колледж автоматизации и информационных технологий № 20",
        "кaит 20": "колледж автоматизации и информационных технологий № 20",
        "кс 54": "колледж связи № 54 имени п.м. вострухина",
        "ит москва": "ит.москва",
        "26 кадр": "26 кадр",
        "мгпу": "мгпу",
        "испо ушинского": "институт среднего профессионального образования имени к. д. ушинского",
        "ушинского": "институт среднего профессионального образования имени к. д. ушинского",
        "колледж добрых дел": "московский колледж социальных профессий имени е.и. холостовой",
        "кдд": "московский колледж социальных профессий имени е.и. холостовой",
        "колледж красина": "московский техникум креативных индустрий им. л.б. красина",
        "техникум красина": "московский техникум креативных индустрий им. л.б. красина",
        "красина": "московский техникум креативных индустрий им. л.б. красина",
        "мгпи": "мгпу институт среднего профессионального образования имени к. д. ушинского",
        "мпк": "московский педагогический колледж",
        "московский педагогический колледж": "московский педагогический колледж",
        "колледж полиции": "колледж полиции",
        "финансовый колледж 35": "финансовый колледж № 35",
    }

    if re.search(r"(^|\s)мпк($|\s)", query_lower):
        if "московский педагогический колледж" in college_name:
            return 4.00
        # МПК не равно ММПК, МИПК, МПТ и прочие похожие сокращения.
        if (
            "музыкально" in college_name
            or "издательско" in college_name
            or "приборостроительный" in college_name
            or "полиграф" in college_name
        ):
            return -3.00

    if "мгпу" in query_lower and "мгпу" in college_name:
        return 2.80

    normalized_query = query_lower
    for short_name, full_name in compact_variants.items():
        if short_name in normalized_query and full_name in college_name:
            return 2.60

    if college_name and college_name in normalized_query:
        return 3.00

    return 0.0


class Retriever:
    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or Embedder()

    def search(
        self,
        db: Session,
        query: str,
        top_k: int | None = None,
        diversify_by_college: bool = True,
    ) -> list[Document]:
        k = top_k or settings.top_k
        logger.info(f"Поиск по запросу: {query}")

        query_embedding = self.embedder.encode(query)
        documents = db.scalars(select(Document)).all()
        faq_like = is_faq_like_query(query)

        scored_documents: list[
            tuple[float, float, float, float, float, float, float, float, Document]
        ] = []

        for doc in documents:
            semantic = cosine_similarity(query_embedding, doc.embedding_json)
            lexical = keyword_score(query, doc)
            domain = domain_score(query, doc)
            anchor = anchor_score(query, doc)
            specialty_bonus = specialty_priority_score(doc, faq_like)
            preferred_bonus = preferred_college_score(query, doc)
            exact_college_bonus = exact_college_match_score(query, doc)
            university_downrank = university_penalty(doc)

            final_score = (
                semantic
                + lexical
                + domain
                + anchor
                + specialty_bonus
                + preferred_bonus
                + exact_college_bonus
                + university_downrank
            )

            if faq_like and doc.doc_type != "faq":
                final_score -= 0.15

            scored_documents.append(
                (
                    final_score,
                    semantic,
                    lexical,
                    domain,
                    anchor,
                    preferred_bonus,
                    exact_college_bonus,
                    university_downrank,
                    doc,
                )
            )

        scored_documents.sort(key=lambda x: x[0], reverse=True)

        if not diversify_by_college:
            result = [doc for *_scores, doc in scored_documents[:k]]
            logger.info(f"Возвращено документов без диверсификации: {len(result)}")
            return result

        unique_documents: list[Document] = []
        seen_colleges: set[str] = set()

        for final, sem, lex, dom, anc, pref, exact, uni_penalty, doc in scored_documents:
            college_name = str(doc.metadata_json.get("college_name", "")).strip()

            if doc.doc_type == "faq" and faq_like:
                unique_documents.append(doc)
            elif college_name:
                if college_name in seen_colleges:
                    continue
                unique_documents.append(doc)
                seen_colleges.add(college_name)
            else:
                unique_documents.append(doc)

            if len(unique_documents) >= k:
                break

        logger.info(f"Найдено уникальных документов: {len(unique_documents)}")
        return unique_documents
