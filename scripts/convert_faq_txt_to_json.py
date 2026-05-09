import json
import re
from pathlib import Path


INPUT_FILE = Path("data.txt")
OUTPUT_FILE = Path("data/faq_admission.json")


SECTION_CATEGORY_MAP = {
    "Как подать заявление": "admission_application",
    "Поступление лиц с ОВЗ и инвалидностью": "ovz_disability",
    "Эксперимент по расширению доступности СПО": "spo_experiment",
    "Сроки подачи заявления и зачисления": "deadlines",
    "Вступительные испытания": "entrance_exams",
    "Документы для зачисления": "enrollment_documents",
    "Поступление в колледж иностранных граждан": "foreign_citizens",
    "Льготы и индивидуальные достижения": "benefits_achievements",
    "Отсрочка от армии": "military_deferral",
    "Практика, стажировки, трудоустройство": "practice_employment",
    "Целевое обучение": "targeted_education",
    "Поступление в ВУЗ после колледжа": "university_after_college",
    "Другие вопросы": "other_questions",
}


SECTION_TAGS_MAP = {
    "Как подать заявление": ["mos.ru", "заявление", "поступление"],
    "Поступление лиц с ОВЗ и инвалидностью": ["ОВЗ", "инвалидность", "поступление"],
    "Эксперимент по расширению доступности СПО": ["СПО", "эксперимент", "ГИА"],
    "Сроки подачи заявления и зачисления": ["сроки", "зачисление", "поступление"],
    "Вступительные испытания": ["вступительные испытания"],
    "Документы для зачисления": ["документы", "зачисление"],
    "Поступление в колледж иностранных граждан": ["иностранные граждане", "поступление"],
    "Льготы и индивидуальные достижения": ["льготы", "индивидуальные достижения"],
    "Отсрочка от армии": ["армия", "отсрочка"],
    "Практика, стажировки, трудоустройство": ["практика", "стажировка", "трудоустройство"],
    "Целевое обучение": ["целевое обучение"],
    "Поступление в ВУЗ после колледжа": ["ВУЗ", "после колледжа"],
    "Другие вопросы": ["faq"],
}


def clean_text(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_question(text: str) -> str:
    return clean_text(text).replace("  ", " ")

def override_section_and_category(question: str, default_section: str) -> tuple[str, str]:
    q = question.lower()

    if "mos.ru" in q or "заявлен" in q:
        return "Как подать заявление", "admission_application"

    if "документ" in q and ("зачислен" in q or "принести" in q or "подач" in q):
        return "Документы для зачисления", "enrollment_documents"

    if "вступительн" in q:
        return "Вступительные испытания", "entrance_exams"

    if "овз" in q or "инвалид" in q:
        return "Поступление лиц с ОВЗ и инвалидностью", "ovz_disability"

    if "гиа" in q or "огэ" in q or "гвэ" in q or "9 класс" in q or "11 класс" in q:
        return "Эксперимент по расширению доступности СПО", "spo_experiment"

    if "иностран" in q or "апостиль" in q or "нострификац" in q:
        return "Поступление в колледж иностранных граждан", "foreign_citizens"

    if "льгот" in q or "индивидуальн" in q or "первоочеред" in q or "преимуществен" in q:
        return "Льготы и индивидуальные достижения", "benefits_achievements"

    if "арм" in q or "военная кафедра" in q:
        return "Отсрочка от армии", "military_deferral"

    if "практик" in q or "трудоустрой" in q or "работу с учеб" in q:
        return "Практика, стажировки, трудоустройство", "practice_employment"

    if "целев" in q:
        return "Целевое обучение", "targeted_education"

    if "вуз" in q or "егэ" in q:
        return "Поступление в ВУЗ после колледжа", "university_after_college"

    return default_section, SECTION_CATEGORY_MAP.get(default_section, slugify(default_section))


def normalize_answer(text: str) -> str:
    text = clean_text(text)

    # Чиним частые косяки пунктуации/пробелов
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s*:\s*", ": ", text)
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        " ": "_",
        "-": "_",
        "ё": "е",
        "й": "i",
        "ц": "ts",
        "у": "u",
        "к": "k",
        "е": "e",
        "н": "n",
        "г": "g",
        "ш": "sh",
        "щ": "sch",
        "з": "z",
        "х": "h",
        "ъ": "",
        "ф": "f",
        "ы": "y",
        "в": "v",
        "а": "a",
        "п": "p",
        "р": "r",
        "о": "o",
        "л": "l",
        "д": "d",
        "ж": "zh",
        "э": "e",
        "я": "ya",
        "ч": "ch",
        "с": "s",
        "м": "m",
        "и": "i",
        "т": "t",
        "ь": "",
        "б": "b",
        "ю": "yu",
    }

    result = []
    for ch in text:
        if ch.isalnum() or ch in " _-":
            result.append(replacements.get(ch, ch))
    slug = "".join(result)
    slug = re.sub(r"[^a-zA-Z0-9_]+", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "faq"


def detect_section_header(line: str) -> str | None:
    """
    Ловит строки вида:
    1. Вступительные испытания
    2. Поступление лиц с ОВЗ и инвалидностью
    """
    match = re.match(r"^\s*\d+\.\s+(.+?)\s*$", line)
    if match:
        return match.group(1).strip()
    return None


def is_question_line(line: str) -> bool:
    line = line.strip()
    return bool(line) and line.endswith("?") and len(line) > 5


def build_tags(section_title: str, question: str, answer: str) -> list[str]:
    tags = list(SECTION_TAGS_MAP.get(section_title, ["faq"]))
    combined = f"{question} {answer}".lower()

    extra_rules = {
        "mos.ru": ["mos.ru"],
        "гия": ["ГИА"],
        "огэ": ["ОГЭ"],
        "гвэ": ["ГВЭ"],
        "вступительн": ["вступительные испытания"],
        "документ": ["документы"],
        "льгот": ["льготы"],
        "общежити": ["общежитие"],
        "стипенди": ["стипендия"],
        "арм": ["армия"],
        "иностран": ["иностранные граждане"],
        "практик": ["практика"],
        "трудоустрой": ["трудоустройство"],
        "вуз": ["ВУЗ"],
        "егэ": ["ЕГЭ"],
        "снилс": ["СНИЛС"],
        "аттестат": ["аттестат"],
    }

    for needle, add_tags in extra_rules.items():
        if needle in combined:
            tags.extend(add_tags)

    # Уникализируем
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)

    return result[:10]


def parse_txt_to_faq_documents(raw_text: str) -> list[dict]:
    lines = [line.rstrip() for line in raw_text.splitlines()]
    docs = []

    current_section = "Другие вопросы"
    current_question = None
    current_answer_lines = []
    faq_counter = 1

    def flush_current():
        nonlocal current_question, current_answer_lines, faq_counter

        if not current_question:
            return

        answer = normalize_answer("\n".join(current_answer_lines))
        question = normalize_question(current_question)

        if not answer:
            current_question = None
            current_answer_lines = []
            return

        final_section, category = override_section_and_category(question, current_section)
        tags = build_tags(final_section, question, answer)

        docs.append(
            {
                "id": f"faq_{faq_counter:03d}",
                "doc_type": "faq",
                "title": question,
                "content": answer,
                "metadata_json": {
                    "section": final_section,
                    "category": category,
                    "tags": tags,
                    "applies_to": {
                        "college_names": [],
                        "domain_tags": [],
                        "specialty_names": [],
                    },
                    "source_type": "manual",
                    "priority": 1,
                },
            }
        )
        faq_counter += 1
        current_question = None
        current_answer_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            # пустые строки просто сохраняем как разрывы внутри ответа
            if current_question and current_answer_lines:
                current_answer_lines.append("")
            continue

        section_header = detect_section_header(line)
        if section_header:
            flush_current()
            current_section = section_header
            continue

        if is_question_line(line):
            flush_current()
            current_question = line
            current_answer_lines = []
            continue

        if current_question:
            current_answer_lines.append(line)

    flush_current()
    return docs


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Не найден входной файл: {INPUT_FILE}")

    raw_text = INPUT_FILE.read_text(encoding="utf-8")
    docs = parse_txt_to_faq_documents(raw_text)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(docs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Готово. Сохранено FAQ-документов: {len(docs)}")
    print(f"Файл: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()