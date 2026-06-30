from typing import Any

from app.logger import get_logger

logger = get_logger(__name__)


DOMAIN_RULES: dict[str, set[str]] = {
    "it": {
        "программист",
        "программное",
        "программного",
        "программированию",
        "программирование",
        "веб",
        "разработка",
        "разработчик",
        "информационной",
        "информационная",
        "информационных",
        "безопасности",
        "кибербезопасность",
        "кибербез",
        "администрирование",
        "администратор",
        "компьютерные",
        "компьютерных",
        "системы",
        "системное",
        "системный",
        "devops",
        "ml",
        "игр",
        "виртуальной",
        "реальности",
        "базами",
        "данных",
    },
    "design": {
        "графический",
        "дизайнер",
        "дизайн",
        "реклама",
        "иллюстратор",
        "художественное",
        "оформление",
        "моушн-дизайнер",
        "3d-визуализатор",
        "фотограф",
        "фотодизайнер",
    },
    "music": {
        "музыка",
        "музыкант",
        "вокал",
        "вокальное",
        "инструментальное",
        "искусство",
        "эстрады",
        "артист",
        "оркестра",
        "хора",
    },
    "law": {
        "юриспруденция",
        "правоохранительная",
        "полицейский",
        "судьи",
        "судебного",
        "юрист",
        "право",
    },
    "finance": {
        "финансы",
        "банковское",
        "бухгалтерский",
        "бухгалтер",
        "экономика",
        "казначейства",
    },
    "tourism": {
        "туризм",
        "гостеприимство",
        "ресепшн",
        "размещения",
        "пассажирами",
        "сервис",
    },
    "transport": {
        "транспорте",
        "логистике",
        "логист",
        "машиниста",
        "железнодорожного",
        "электропоезда",
        "метрополитене",
        "перевозок",
    },
    "production": {
        "аддитивные",
        "автоматизация",
        "бпла",
        "контролер качества",
        "машиностроение",
        "мехатроника",
        "металлургическое",
        "металлообрабатывающих",
        "наладчик",
        "оператор-наладчик",
        "полимерных",
        "промышленное",
        "промышленного",
        "производственного оборудования",
        "роботизированного",
        "робототехника",
        "сварочное",
        "станков",
        "технологического оборудования",
        "электронных приборов",
    },
    "medicine": {
        "медицинская",
        "медицинский",
        "медицинское",
        "сестринское",
        "стоматология",
        "стоматологическая",
        "зубной",
        "фармация",
        "фармацевт",
        "оптика",
        "оптометрист",
        "массаж",
        "лабораторная диагностика",
        "фельдшер",
        "акушер",
    },
    "construction": {
        "строительство",
        "архитектура",
        "bim",
        "сварщик",
        "сантехнических",
        "вентиляции",
        "водоснабжение",
        "землеустройство",
        "электромонтажник",
        "реставратор",
    },
    "media": {
        "анимация",
        "кино",
        "телепроизводство",
        "актерское",
        "звукорежиссер",
        "звукооператор",
        "дубляжа",
    },
}


def collect_domain_tags(*texts: str) -> list[str]:
    combined_text = " ".join(texts).lower()
    found_tags: list[str] = []

    for domain, keywords in DOMAIN_RULES.items():
        if any(keyword in combined_text for keyword in keywords):
            found_tags.append(domain)

    return sorted(set(found_tags))


def calculate_college_profile_scores(college: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}

    for specialty in college.get("specialties", []):
        specialty_name = specialty.get("name", "")
        professions = specialty.get("professions", [])
        tags = collect_domain_tags(specialty_name, " ".join(professions))

        for tag in tags:
            scores[tag] = scores.get(tag, 0.0) + 1.0

    return scores


def build_college_document(college: dict[str, Any]) -> dict[str, Any]:
    specialties = college.get("specialties", [])
    specialty_names = [spec.get("name", "") for spec in specialties]
    specialty_urls = {
        spec.get("name", ""): spec.get("atlas_url", "")
        for spec in specialties
        if spec.get("name") and spec.get("atlas_url")
    }
    profile_scores = calculate_college_profile_scores(college)

    content_parts = [
        f"Колледж: {college.get('name', '')}",
        f"Алиасы: {', '.join(college.get('aliases', []))}",
        f"Специальности: {', '.join(specialty_names)}",
        f"Адреса: {', '.join(college.get('addresses', []))}",
        f"Контакты: {', '.join(college.get('contacts', []))}",
        f"Сайт: {college.get('website', '')}",
    ]

    return {
        "doc_type": "college",
        "title": college.get("name", ""),
        "content": "\n".join(content_parts),
        "metadata_json": {
            "college_name": college.get("name", ""),
            "aliases": college.get("aliases", []),
            "addresses": college.get("addresses", []),
            "contacts": college.get("contacts", []),
            "website": college.get("website", ""),
            "atlas_url": college.get("atlas_url", ""),
            "specialties": specialty_names,
            "specialty_urls": specialty_urls,
            "domain_tags": collect_domain_tags(
                college.get("name", ""),
                " ".join(specialty_names),
            ),
            "college_profile_scores": profile_scores,
        },
    }


def build_specialty_documents(college: dict[str, Any]) -> list[dict[str, Any]]:
    documents = []
    profile_scores = calculate_college_profile_scores(college)

    for specialty in college.get("specialties", []):
        specialty_name = specialty.get("name", "")
        professions = specialty.get("professions", [])
        specialty_url = specialty.get("atlas_url", "")
        domain_tags = collect_domain_tags(specialty_name, " ".join(professions))

        content_parts = [
            f"Колледж: {college.get('name', '')}",
            f"Специальность: {specialty_name}",
            f"Профессии: {', '.join(professions)}",
            f"Адреса: {', '.join(college.get('addresses', []))}",
            f"Контакты: {', '.join(college.get('contacts', []))}",
            f"Сайт: {college.get('website', '')}",
        ]
        if specialty_url:
            content_parts.append(f"Атлас профессий: {specialty_url}")

        documents.append(
            {
                "doc_type": "specialty",
                "title": f"{college.get('name', '')} — {specialty_name}",
                "content": "\n".join(content_parts),
                "metadata_json": {
                    "college_name": college.get("name", ""),
                    "specialty_name": specialty_name,
                    "professions": professions,
                    "addresses": college.get("addresses", []),
                    "contacts": college.get("contacts", []),
                    "website": college.get("website", ""),
                    "atlas_url": college.get("atlas_url", ""),
                    "specialty_url": specialty_url,
                    "domain_tags": domain_tags,
                    "college_profile_scores": profile_scores,
                },
            }
        )

    return documents


def build_all_documents(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logger.info("Сборка документов для RAG...")

    documents = []

    for college in data:
        documents.append(build_college_document(college))
        documents.extend(build_specialty_documents(college))

    logger.info(f"Собрано документов: {len(documents)}")
    return documents
