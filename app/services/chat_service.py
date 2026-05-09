import random
import re
from collections import Counter
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.repository import Document
from app.logger import get_logger
from app.rag.retriever import Retriever
from app.services.session_service import SessionService
from app.llm.ollama_client import OllamaClient
from app.services.dialog_router import DialogRouter, RouterDecision

logger = get_logger(__name__)


GREETING_MARKERS = {
    "привет",
    "здравствуйте",
    "здравствуй",
    "здарова",
    "ку",
    "hello",
    "hi",
}

FAREWELL_MARKERS = {
    "пока",
    "до свидания",
    "нет спасибо",
    "дальше я сам",
    "спасибо, пока",
    "bye",
    "goodbye",
}

INTRO_MARKERS = {
    "кто ты",
    "что ты",
    "что ты умеешь",
    "что ты можешь",
    "чем ты помогаешь",
}

FAQ_HINTS = [
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
    "вступительные испытания",
    "экзамены",
]

CAREER_HINTS = [
    "хочу стать",
    "мечтаю стать",
    "кем стать",
    "куда поступать",
    "куда мне поступать",
    "на кого поступать",
    "где учиться",
    "что выбрать",
    "какую специальность",
    "какие колледжи",
    "посоветуй колледжи",
    "что посоветуешь",
]

DETAIL_HINTS = [
    "расскажи про",
    "подробнее про",
    "расскажи подробнее",
    "расскажи мне об",
    "расскажи об",
    "что за колледж",
    "что можешь сказать про",
    "адрес",
    "адреса",
    "контакты",
    "сайт",
]

FOLLOWUP_SIMPLIFY_MARKERS = {
    "давай",
    "объясни проще",
    "проще",
    "простыми словами",
    "объясни по простому",
    "объясни простыми словами",
}

FOLLOWUP_DETAIL_MARKERS = {
    "подробнее",
    "расскажи подробнее",
    "давай подробнее",
    "подробней",
}

FOLLOWUP_CONFIRM_MARKERS = {
    "ок",
    "хорошо",
    "да",
    "ага",
    "давай",
}


ABUSE_MARKERS = {
    "пидор",
    "нахуй",
    "хуй",
    "уеб",
    "ебан",
    "беспонтовый",
    "позорный",
    "чмо",
    "тупой",
    "дурак",
    "дура",
    "еблан",
    "говно",
    "уебищ",
}

OUT_OF_SCOPE_MARKERS = {
    "напиши алгоритм",
    "реши алгоритм",
    "реши задачу",
    "напиши код",
    "бинарного поиска",
    "сделай домашку",
    "теорема",
    "теорему",
    "лагранжа",
    "математика",
    "физика",
    "python",
    "java",
    "javascript",
}

DRAWING_HINTS = {
    "рисовать",
    "рисую",
    "картины",
    "живопись",
    "художник",
    "арт",
    "иллюстрация",
}

FASHION_HINTS = {
    "мода",
    "одежда",
    "костюм",
    "костюмы",
    "художник по костюму",
    "дизайнер одежды",
}

PEDAGOGY_HINTS = {
    "пед",
    "педагог",
    "педагогика",
    "учитель",
    "мгпу",
    "ушинского",
    "испо",
}

KNOWN_COLLEGE_ALIASES = {
    "каит 20": "Колледж автоматизации и информационных технологий № 20",
    "кaит 20": "Колледж автоматизации и информационных технологий № 20",
    "ит.москва": "ИТ.Москва",
    "ит москва": "ИТ.Москва",
    "кс 54": "Колледж связи № 54 имени П.М. Вострухина",
    "26 кадр": "Колледж Архитектуры, Дизайна и Реинжиниринга № 26",
    "мгпу": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    "испо ушинского": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    "ушинского": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    "колледж добрых дел": "Московский колледж социальных профессий имени Е.И. Холостовой",
    "кдд": "Московский колледж социальных профессий имени Е.И. Холостовой",
    "мпк": "Московский педагогический колледж",
    "московский педагогический колледж": "Московский педагогический колледж",
    "ммпк": "Московский музыкально-педагогический колледж",
    "музыкально-педагогический": "Московский музыкально-педагогический колледж",
    "колледж полиции": "Колледж полиции",
    "финансовый колледж 35": "Финансовый колледж № 35",
    "колледж красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "техникум красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "мгпи": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
}

CONTEXTUAL_FOLLOWUP_MARKERS = {
    "а как",
    "а если",
    "что делать",
    "что дальше",
    "что меня ждет",
    "что меня ждёт",
    "как узнать",
    "меня ждет",
    "меня ждёт",
    "не понравится",
    "подойдет ли",
    "подойдёт ли",
    "что будет после",
}

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")


class ChatService:
    def __init__(
        self,
        retriever: Retriever | None = None,
        session_service: SessionService | None = None,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self.retriever = retriever or Retriever()
        self.session_service = session_service or SessionService()
        self.llm_client = llm_client or OllamaClient()
        self.dialog_router = DialogRouter(llm_client=self.llm_client)

    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s№.-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_plain_greeting(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in GREETING_MARKERS

    def is_intro_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return any(marker in q for marker in INTRO_MARKERS)

    def is_farewell(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in FAREWELL_MARKERS

    def is_college_count_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        has_college = "колледж" in q or "колледжей" in q
        has_count = any(
            phrase in q
            for phrase in ["сколько", "какое количество", "сколько всего", "сколько существует"]
        )
        return has_college and has_count

    def is_faq_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        if any(marker in q for marker in CAREER_HINTS):
            return False
        return any(hint in q for hint in FAQ_HINTS)

    def is_detail_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return any(marker in q for marker in DETAIL_HINTS)

    def is_followup_for_simplify(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in FOLLOWUP_SIMPLIFY_MARKERS

    def is_followup_for_detail(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in FOLLOWUP_DETAIL_MARKERS

    def is_short_followup(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in FOLLOWUP_CONFIRM_MARKERS or len(q.split()) <= 2


    def is_abusive_without_task(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        has_abuse = any(marker in q for marker in ABUSE_MARKERS)
        has_task = (
            self.is_faq_query(q)
            or self.is_detail_query(q)
            or any(marker in q for marker in CAREER_HINTS)
            or any(marker in q for marker in DRAWING_HINTS | FASHION_HINTS | PEDAGOGY_HINTS)
        )
        return has_abuse and not has_task

    def is_gibberish(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        if len(q) < 12:
            return False

        words = re.findall(r"[а-яa-zё]+", q)
        if not words:
            return True

        # Длинные нормальные русские слова не считаем мусором: педагогические, профессиональное и т.п.
        if any(re.search(r"[а-яё]{6,}", word) for word in words):
            return False

        repeated = any(len(set(word)) <= 2 and len(word) >= 12 for word in words)
        long_latin = any(re.search(r"[a-z]{14,}", word) for word in words)
        return repeated or long_latin

    def is_out_of_scope_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return any(marker in q for marker in OUT_OF_SCOPE_MARKERS)

    def is_duration_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return any(
            marker in q
            for marker in [
                "сколько лет",
                "сколько учиться",
                "сколько длится",
                "срок обучения",
                "длительность обучения",
            ]
        )

    def is_general_explain_followup(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return q in {"объясни", "поясни", "что это значит", "расскажи проще", "простыми словами"}

    def is_more_specialties_followup(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        return any(
            marker in q
            for marker in [
                "какие еще специальности",
                "какие ещё специальности",
                "какие специальности есть",
                "что еще есть",
                "что ещё есть",
            ]
        )

    def extract_last_known_college_from_text(self, text: str) -> str | None:
        normalized = self.normalize_text(text)
        for alias, canonical in KNOWN_COLLEGE_ALIASES.items():
            if alias in normalized:
                return canonical

        known_full_names = [
            "колледж автоматизации и информационных технологий № 20",
            "колледж связи № 54 имени п.м. вострухина",
            "мгпу институт среднего профессионального образования имени к. д. ушинского",
            "московский колледж социальных профессий имени е.и. холостовой",
            "колледж архитектуры дизайна и реинжиниринга № 26",
        ]
        for name in known_full_names:
            if name in normalized:
                return name
        return None

    def contains_cjk(self, text: str) -> bool:
        return bool(CJK_RE.search(text))

    def clean_llm_output(self, text: str) -> str:
        # Если модель внезапно ушла в китайский/японский/корейский, режем ответ до первого такого символа.
        # Если после обрезки получается слишком мало смысла — включится fallback.
        match = CJK_RE.search(text)
        if match:
            text = text[: match.start()].strip()

        text = re.sub(r"#+\s*", "", text)
        text = text.replace("Коллеги,", "")
        text = text.replace("коллеги,", "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def is_explicit_known_college_query(self, user_query: str) -> bool:
        return self.extract_last_known_college_from_text(user_query) is not None

    def is_contextual_followup(self, user_query: str) -> bool:
        q = self.normalize_text(user_query)
        if self.is_detail_query(q) or self.is_faq_query(q) or self.is_explicit_known_college_query(q):
            return False
        if self.is_general_explain_followup(q) or self.is_followup_for_simplify(q) or self.is_followup_for_detail(q):
            return True
        if any(marker in q for marker in CONTEXTUAL_FOLLOWUP_MARKERS):
            return True
        return len(q.split()) <= 5 and any(word in q for word in {"это", "так", "там", "туда", "дальше"})

    def find_last_meaningful_user_message(self, messages) -> str:
        for msg in reversed(messages):
            if getattr(msg, "role", "") != "user":
                continue
            content = getattr(msg, "content", "")
            if not content:
                continue
            if self.is_plain_greeting(content) or self.is_abusive_without_task(content) or self.is_out_of_scope_query(content):
                continue
            if self.is_general_explain_followup(content) or self.is_followup_for_simplify(content):
                continue
            return content
        return ""

    def render_scope_boundary(self, user_query: str) -> str:
        if self.is_out_of_scope_query(user_query):
            return (
                "Я здесь именно как помощник по колледжам Москвы и поступлению. "
                "Алгоритмы и учебный код лучше разбирать отдельно.\n\n"
                "Но если вопрос связан с выбором направления, могу подсказать, где учиться на программиста."
            )

        return (
            "Давай без оскорблений. Я могу помочь с колледжами Москвы, специальностями и поступлением.\n\n"
            "Напиши нормальный запрос: например, «куда пойти на IT», «какие документы нужны» или «расскажи про КАИТ 20»."
        )

    def render_ovz_faq_answer(self, q_norm: str) -> str:
        if "льгот" in q_norm:
            return (
                "По моей базе я не могу подтвердить отдельную льготу именно на зачисление для инвалидов или лиц с ОВЗ.\n\n"
                "Но в базе есть важный факт: при вступительных испытаниях могут создать специальные условия с учётом состояния здоровья и индивидуальных возможностей поступающего. "
                "Для этого нужно указать необходимость специальных условий в заявлении и предоставить подтверждающий документ, например документ об инвалидности, заключение ЦПМПК или ИПРА — в зависимости от ситуации.\n\n"
                "Чтобы не ошибиться, лучше заранее обратиться в приёмную комиссию конкретного колледжа: они скажут, какие документы нужны именно тебе."
            )
        return (
            "Если ты не можешь проходить вступительные испытания на общих условиях, при поступлении можно запросить специальные условия.\n\n"
            "Обычно для этого в заявлении указывают, какие условия нужны, и прикладывают документ, подтверждающий инвалидность или ОВЗ. Это может быть документ об инвалидности, заключение ЦПМПК или индивидуальная программа реабилитации и абилитации — зависит от ситуации.\n\n"
            "Я бы советовал до подачи заявления связаться с приёмной комиссией выбранного колледжа или прийти на день открытых дверей: там точнее скажут, какие документы подготовить и как организуют вступительные испытания."
        )

    def render_no_duration_data(self, user_query: str, documents: list[Document]) -> str:
        specialty_names: list[str] = []
        for doc in documents:
            spec = self.extract_specialty_name(doc)
            if spec and spec not in specialty_names:
                specialty_names.append(spec)

        if specialty_names:
            return (
                "В моей базе по этой специальности есть названия колледжей, специальности и профессии после обучения, "
                "но точный срок обучения здесь не указан.\n\n"
                f"Речь, похоже, про: {', '.join(specialty_names[:3])}.\n\n"
                "Чтобы не соврать, срок лучше проверить на странице приёмной комиссии конкретного колледжа. "
                "Если хочешь, я могу подсказать, какие колледжи смотреть по этой специальности."
            )

        return (
            "В моей базе нет точного срока обучения по этому направлению. "
            "Чтобы не соврать, лучше проверять срок на сайте конкретного колледжа или в правилах приёма."
        )

    def get_colleges_count(self, db: Session) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.doc_type == "college")
        result = db.scalar(stmt)
        return int(result or 0)

    def extract_college_name(self, doc: Document) -> str:
        return str(doc.metadata_json.get("college_name", "")).strip()

    def extract_specialty_name(self, doc: Document) -> str:
        return str(doc.metadata_json.get("specialty_name", "")).strip()

    def canonical_college_from_text(self, text: str) -> str | None:
        normalized = self.normalize_text(text).replace("ё", "е")
        # МПК — строго педагогический, ММПК — только музыкальный.
        if re.search(r"(^|\s)мпк($|\s)", normalized):
            return "Московский педагогический колледж"
        if "ммпк" in normalized or "музыкально педагогический" in normalized or "музыкально-педагогический" in normalized:
            return "Московский музыкально-педагогический колледж"
        for alias, canonical in KNOWN_COLLEGE_ALIASES.items():
            if alias in {"мпк", "ммпк"}:
                continue
            if alias in normalized:
                return canonical
        return None

    def college_name_matches(self, actual: str, canonical: str) -> bool:
        a = self.normalize_text(actual).replace("ё", "е")
        c = self.normalize_text(canonical).replace("ё", "е")
        if not a or not c:
            return False
        if a == c or c in a or a in c:
            return True
        # Для МГПУ ИСПО Ушинского в базе название может быть укорочено.
        if "ушинского" in c and "ушинского" in a:
            return True
        if "красина" in c and "красина" in a:
            return True
        return False

    def get_all_specialty_docs_for_college(self, db: Session, college_name: str) -> list[Document]:
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()
        matched = [doc for doc in docs if self.college_name_matches(self.extract_college_name(doc), college_name)]
        # Дедуп по специальности, чтобы не повторять одно и то же.
        seen: set[str] = set()
        unique: list[Document] = []
        for doc in matched:
            spec = self.extract_specialty_name(doc)
            key = self.normalize_text(spec)
            if not spec or key in seen:
                continue
            seen.add(key)
            unique.append(doc)
        unique.sort(key=lambda d: self.extract_specialty_name(d).lower())
        return unique

    def get_college_card_for_name(self, db: Session, college_name: str) -> Document | None:
        docs = db.scalars(select(Document).where(Document.doc_type == "college")).all()
        for doc in docs:
            if self.college_name_matches(self.extract_college_name(doc), college_name):
                return doc
        return None

    def render_all_specialties_for_college(self, db: Session, college_name: str) -> str:
        specialty_docs = self.get_all_specialty_docs_for_college(db, college_name)
        college_card = self.get_college_card_for_name(db, college_name)
        display_name = self.extract_college_name(college_card) if college_card else college_name

        if not specialty_docs:
            return (
                f"Я не нашёл в базе список специальностей для колледжа: {display_name}. "
                "Лучше сверить актуальный перечень на сайте колледжа или в приёмной комиссии."
            )

        lines = [f"{display_name}: в моей базе вижу такие специальности:"]
        for idx, doc in enumerate(specialty_docs, start=1):
            spec = self.extract_specialty_name(doc)
            professions = doc.metadata_json.get("professions", []) or []
            line = f"{idx}. {spec}"
            if professions:
                line += f" — после обучения: {', '.join(str(p) for p in professions[:3])}"
            lines.append(line)

        if college_card:
            contacts = college_card.metadata_json.get("contacts", []) or []
            website = college_card.metadata_json.get("website", "") or college_card.metadata_json.get("site", "")
            if website:
                lines.append(f"Сайт: {website}")
            if contacts:
                lines.append(f"Контакты: {'; '.join(str(c) for c in contacts[:4])}")

        lines.append("Если список на сайте колледжа шире, лучше сверить его с приёмной комиссией: база могла устареть.")
        return "\n".join(lines)

    def is_all_specialties_request(self, text: str) -> bool:
        q = self.normalize_text(text).replace("ё", "е")
        return any(marker in q for marker in [
            "все специальности", "все специальности", "какие специальности", "какие еще специальности",
            "какие ещё специальности", "остальные специальности", "специальности там есть",
            "специальности есть", "их больше",
        ])

    def extract_ordinal_request(self, text: str) -> int | None:
        q = self.normalize_text(text).replace("ё", "е")
        mapping = {
            "перв": 1, "1": 1,
            "втор": 2, "2": 2,
            "трет": 3, "3": 3,
            "четвер": 4, "4": 4,
            "пят": 5, "5": 5,
            "шест": 6, "6": 6,
            "седьм": 7, "7": 7,
            "восьм": 8, "8": 8,
            "девят": 9, "9": 9,
            "десят": 10, "10": 10,
        }
        if "специальн" not in q and "пункт" not in q and "вариант" not in q:
            return None
        for marker, num in mapping.items():
            if marker in q:
                return num
        return None

    def parse_last_numbered_specialties(self, messages) -> tuple[str | None, list[str]]:
        """Ищет последний полноценный нумерованный список специальностей.

        Важно: если пользователь сначала попросил подробнее про 3-ю специальность,
        последний ответ уже будет карточкой одной специальности. Поэтому нельзя брать
        только последний assistant message — надо пройти историю назад и найти список,
        где есть хотя бы 2 пункта.
        """
        for msg in reversed(messages):
            if getattr(msg, "role", "") != "assistant":
                continue
            text = str(getattr(msg, "content", ""))
            college = self.canonical_college_from_text(text)
            specs: list[str] = []
            for line in text.splitlines():
                raw = line.strip()
                m = re.match(r"^(\d+)\.\s+(.*)$", raw)
                if not m:
                    continue
                item = re.sub(r"\*", "", m.group(2)).strip()
                item = re.split(r"\s+—\s+|\s+-\s+|:", item, maxsplit=1)[0].strip()
                # Отсекаем строки типа "Колледж:" / "Адреса:" / обычные рекомендации.
                bad_prefixes = ("колледж", "адрес", "контакт", "сайт", "почему", "следующий шаг")
                if item and not item.lower().startswith(bad_prefixes):
                    specs.append(item)
            if len(specs) >= 2:
                return college, specs
        return None, []

    def render_specialty_detail_by_name(self, db: Session, specialty_name: str, college_name: str | None = None) -> str:
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()
        target = self.normalize_text(specialty_name).replace("ё", "е")
        candidates: list[Document] = []
        for doc in docs:
            spec = self.normalize_text(self.extract_specialty_name(doc)).replace("ё", "е")
            if not spec:
                continue
            if target in spec or spec in target:
                if college_name is None or self.college_name_matches(self.extract_college_name(doc), college_name):
                    candidates.append(doc)
        if not candidates:
            return (
                f"Я понял, что речь про специальность «{specialty_name}», но не нашёл по ней точной карточки в базе. "
                "Лучше сверить описание на сайте колледжа или уточнить в приёмной комиссии."
            )
        doc = candidates[0]
        college = self.extract_college_name(doc)
        spec = self.extract_specialty_name(doc)
        professions = doc.metadata_json.get("professions", []) or []
        lines = [f"{spec} — что видно по моей базе:"]
        if college:
            lines.append(f"Колледж: {college}")
        if professions:
            lines.append(f"После обучения можно ориентироваться на профессии: {', '.join(str(p) for p in professions[:5])}.")
        content = re.sub(r"\s+", " ", (doc.content or "")).strip()
        if content:
            lines.append(content[:900])
        lines.append("Если хочешь понять, подходит ли это направление, лучше посмотреть программу на сайте колледжа или сходить на день открытых дверей.")
        return "\n".join(lines)

    def get_recent_messages_safe(self, db: Session, session, limit: int = 10):
        try:
            return self.session_service.get_recent_messages(db=db, session=session, limit=limit)
        except Exception as e:
            logger.warning(f"Не удалось получить историю сообщений: {e}")
            return []

    def find_last_assistant_message(self, messages) -> str:
        for msg in reversed(messages):
            if getattr(msg, "role", "") == "assistant":
                return getattr(msg, "content", "")
        return ""

    def find_last_user_message(self, messages) -> str:
        for msg in reversed(messages):
            if getattr(msg, "role", "") == "user":
                return getattr(msg, "content", "")
        return ""

    def build_retrieval_query(self, user_query: str, recent_messages) -> str:
        q = user_query.strip()
        if not recent_messages:
            return q

        previous_messages = recent_messages[:-1]
        last_user = self.find_last_user_message(previous_messages)
        last_meaningful_user = self.find_last_meaningful_user_message(previous_messages)
        last_assistant = self.find_last_assistant_message(previous_messages)
        normalized = self.normalize_text(q)

        if self.is_followup_for_simplify(q) or self.is_general_explain_followup(q):
            if last_assistant:
                return f"Объясни проще в контексте прошлого ответа: {last_assistant}"
            return q

        if self.is_more_specialties_followup(q):
            topic = self.extract_last_known_college_from_text(last_assistant) or self.extract_last_known_college_from_text(last_user)
            if topic:
                return f"{topic}. Какие специальности есть в этом колледже?"
            if last_meaningful_user:
                return f"{last_meaningful_user}. {q}"
            return q

        if self.is_followup_for_detail(q):
            topic = self.extract_last_known_college_from_text(last_assistant) or self.extract_last_known_college_from_text(last_user)
            if topic:
                return f"{topic}. Подробнее."
            if last_meaningful_user:
                return f"{last_meaningful_user}. Подробно: {q}"
            return q

        pronoun_markers = {"этот", "эта", "это", "он", "она", "они", "туда", "там", "про него", "про неё"}
        if self.is_contextual_followup(q) or any(marker in normalized for marker in pronoun_markers):
            topic = self.extract_last_known_college_from_text(last_assistant) or self.extract_last_known_college_from_text(last_meaningful_user)
            if topic:
                return f"{topic}. Предыдущая тема: {last_meaningful_user}. Уточнение пользователя: {q}"
            if last_meaningful_user:
                return f"Предыдущая тема: {last_meaningful_user}. Уточнение пользователя: {q}"
            if last_assistant:
                return f"Предыдущий ответ: {last_assistant}. Уточнение пользователя: {q}"
            return q

        return q

    def choose_mode(self, user_query: str, documents: list[Document], recent_messages) -> str:
        if self.is_faq_query(user_query):
            return "faq"

        if self.is_detail_query(user_query) or self.is_explicit_known_college_query(user_query):
            return "detail"

        if self.is_general_explain_followup(user_query):
            return "context"

        if self.is_more_specialties_followup(user_query):
            return "detail"

        normalized = self.normalize_text(user_query)

        if self.is_contextual_followup(user_query):
            return "context"

        if any(marker in normalized for marker in DRAWING_HINTS | FASHION_HINTS | PEDAGOGY_HINTS):
            return "recommend"

        if self.is_followup_for_simplify(user_query):
            last_assistant = self.find_last_assistant_message(recent_messages[:-1])
            if "Если хочешь, могу объяснить это проще" in last_assistant:
                return "faq_simple"
            return "context"

        if any(marker in normalized for marker in CAREER_HINTS):
            return "recommend"

        if documents:
            first = documents[0]
            if first.doc_type == "college":
                return "detail"

            college_names = [self.extract_college_name(doc) for doc in documents[:5] if self.extract_college_name(doc)]
            unique_colleges = {name for name in college_names if name}
            if len(unique_colleges) == 1 and "колледж" in normalized:
                return "detail"

            faq_top = sum(1 for doc in documents[:3] if doc.doc_type == "faq")
            if faq_top >= 2:
                return "faq"

            return "recommend"

        return "clarify"

    def doc_brief(self, doc: Document) -> str:
        college_name = self.extract_college_name(doc)
        specialty_name = self.extract_specialty_name(doc)
        professions = doc.metadata_json.get("professions", [])
        doc_type = doc.doc_type

        lines = [f"Тип: {doc_type}"]
        if doc.title:
            lines.append(f"Заголовок: {doc.title}")
        if college_name:
            lines.append(f"Колледж: {college_name}")
        if specialty_name:
            lines.append(f"Специальность: {specialty_name}")
        if professions:
            lines.append(f"Профессии после обучения: {', '.join(professions[:5])}")

        content = (doc.content or "").strip()
        if content:
            compact = re.sub(r"\s+", " ", content)
            lines.append(f"Факты: {compact[:700]}")

        return "\n".join(lines)

    def compact_docs(self, documents: Iterable[Document], limit: int = 5) -> str:
        blocks = []
        for idx, doc in enumerate(list(documents)[:limit], start=1):
            blocks.append(f"[Документ {idx}]\n{self.doc_brief(doc)}")
        return "\n\n".join(blocks)

    def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        result = self.llm_client.generate(prompt).strip()
        return result

    def render_recommendation_fallback(self, documents: list[Document], user_query: str) -> str:
        specialty_docs = [doc for doc in documents if doc.doc_type == "specialty"]
        if not specialty_docs:
            return (
                "Я не вижу в базе точного совпадения под такой запрос. "
                "Могу предложить ближайшие варианты, если ты чуть уточнишь интерес: например, больше тянет к разработке, аналитике, безопасности или системам."
            )

        lines = []
        seen_colleges: set[str] = set()
        added = 0

        for doc in specialty_docs:
            college_name = self.extract_college_name(doc)
            specialty_name = self.extract_specialty_name(doc)
            professions = doc.metadata_json.get("professions", [])

            if not college_name or not specialty_name or college_name in seen_colleges:
                continue

            if added == 0:
                lines.append("Прямого совпадения в базе может не быть, поэтому я покажу ближайшие варианты.")

            lines.append(f"{added + 1}. {college_name} — {specialty_name}")
            if professions:
                lines.append(f"   После обучения: {', '.join(professions[:3])}")
            lines.append("   Почему это может подойти: даёт близкую базу и понятную точку входа в профессию.")
            seen_colleges.add(college_name)
            added += 1

            if added >= 3:
                break

        if added == 0:
            return (
                "Я не нашёл хороших совпадений. Уточни, пожалуйста, что тебе ближе: программирование, аналитика, математика, безопасность или что-то ещё."
            )

        lines.append("")
        lines.append("Если хочешь, я могу дальше коротко объяснить, чем вообще занимается этот специалист и через какие специальности к нему чаще приходят.")
        return "\n".join(lines)

    def render_detail_fallback(self, documents: list[Document]) -> str:
        college_docs = [doc for doc in documents if self.extract_college_name(doc)]
        if not college_docs:
            return "По этому колледжу у меня пока нет достаточных данных в базе."

        target_college = self.extract_college_name(college_docs[0])
        same_college_docs = [doc for doc in college_docs if self.extract_college_name(doc) == target_college]

        college_card = next((doc for doc in same_college_docs if doc.doc_type == "college"), None)
        specialty_docs = [doc for doc in same_college_docs if doc.doc_type == "specialty"][:6]

        lines = [f"{target_college} — коротко:"]

        if specialty_docs:
            lines.append("Что здесь можно изучать:")
            for doc in specialty_docs[:5]:
                spec = self.extract_specialty_name(doc)
                professions = doc.metadata_json.get("professions", [])
                if spec:
                    line = f"- {spec}"
                    if professions:
                        line += f" → после обучения: {', '.join(professions[:2])}"
                    lines.append(line)

        if college_card:
            addresses = college_card.metadata_json.get("addresses", [])
            contacts = college_card.metadata_json.get("contacts", [])
            website = college_card.metadata_json.get("website", "")

            if addresses:
                lines.append("Адреса:")
                for addr in addresses[:4]:
                    lines.append(f"- {addr}")

            if contacts:
                lines.append("Контакты:")
                for contact in contacts[:4]:
                    lines.append(f"- {contact}")

            if website:
                lines.append(f"Сайт: {website}")

        lines.append("")
        lines.append("Если хочешь, я могу следующим сообщением помочь понять, кому этот колледж подойдёт лучше всего.")
        return "\n".join(lines)

    def render_faq_fallback(self, documents: list[Document]) -> str:
        faq_docs = [doc for doc in documents if doc.doc_type == "faq"][:3]
        if not faq_docs:
            return "В моей базе сейчас нет точного FAQ-ответа на этот вопрос."

        answer = faq_docs[0].content.strip()
        answer += "\n\nЕсли хочешь, могу объяснить это проще."
        return answer

    def render_simple_explanation(self, recent_messages) -> str:
        last_assistant = self.find_last_assistant_message(recent_messages[:-1])
        if not last_assistant:
            return "Хорошо. Напиши, что именно объяснить проще, и я переформулирую без сложных формулировок."

        system_prompt = (
            "Ты помощник по колледжам Москвы. Отвечай только на русском языке. "
            "Перепиши объяснение проще и короче, обычным человеческим языком. "
            "Не добавляй новых фактов. Не выдумывай. "
            "Если в тексте есть официальный смысл, сохрани его, но объясни понятнее."
        )
        user_prompt = f"Объясни проще вот этот ответ:\n\n{last_assistant}"
        try:
            result = self.call_llm(system_prompt, user_prompt)
            if result:
                return result
        except Exception as e:
            logger.warning(f"LLM simplify fallback: {e}")

        return "Проще говоря: я могу объяснить ответ обычными словами, но лучше уточни, какой кусок тебе непонятен."

    def build_recommend_prompt(self, user_query: str, documents: list[Document]) -> tuple[str, str]:
        system_prompt = (
            "Ты дружелюбный и точный помощник по колледжам Москвы. "
            "Отвечай только на русском языке. Запрещены китайские, японские, корейские и случайные английские вставки, кроме официальных названий вроде DevOps или ML. "
            "Не используй markdown-заголовки вида ###. Не обращайся 'коллеги'. Лучше обращайся к пользователю на 'ты'. "
            "Нельзя выдумывать факты: не пиши про репутацию, отзывы, практику, работодателей, качество, круглогодичное обучение или связи с компаниями, если этого нет в фактах. "
            "Используй только факты из контекста. "
            "Если прямого совпадения нет, честно скажи об этом одной короткой фразой. "
            "Дай 1-3 ближайших варианта. "
            "По каждому варианту укажи: колледж, специальность, 1-3 профессии после обучения и коротко объясни, почему вариант подходит. "
            "Не дублируй один и тот же колледж больше одного раза. "
            "Ответ должен быть компактным: не больше 1700 символов. "
            "В конце предложи один следующий шаг: объяснить профессию, сравнить варианты или сузить выбор."
        )
        user_prompt = (
            f"Запрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=6)}\n\n"
            "Сделай ответ полезным, естественным и не перегруженным."
        )
        return system_prompt, user_prompt

    def build_detail_prompt(self, user_query: str, documents: list[Document]) -> tuple[str, str]:
        system_prompt = (
            "Ты дружелюбный помощник по колледжам Москвы. "
            "Отвечай только на русском языке. Запрещены китайские, японские, корейские и случайные английские вставки. Не используй markdown-заголовки вида ###. "
            "Нельзя выдумывать факты: не пиши про престиж, отзывы, практику, работодателей, качество, круглогодичное обучение или связи с компаниями, если этого нет в фактах. "
            "Расскажи про конкретный колледж по фактам из контекста. "
            "Структура: коротко что это за колледж; 3-5 заметных специальностей; кем можно работать после; адреса/контакты/сайт, если есть. "
            "Ответ должен быть полезным, но компактным: не больше 2200 символов."
        )
        user_prompt = (
            f"Запрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=8)}\n\n"
            "Сделай ответ живым, но без лишней рекламы."
        )
        return system_prompt, user_prompt

    def build_faq_prompt(self, user_query: str, documents: list[Document]) -> tuple[str, str]:
        system_prompt = (
            "Ты помощник по колледжам Москвы. "
            "Отвечай только на русском языке. Запрещены китайские и английские вставки, кроме официальных терминов. "
            "FAQ-ответ должен быть аккуратным и близким к официальному, но понятным. "
            "Используй только факты из контекста. Не добавляй правил, которых нет в фактах. "
            "Если в вопросе несколько тем, раздели ответ на короткие блоки по темам. "
            "Если точного факта нет, прямо скажи: 'В моей базе нет точного ответа по этой части'. "
            "В конце добавь: 'Если хочешь, могу объяснить это проще.' "
            "Ответ не длиннее 1700 символов."
        )
        user_prompt = (
            f"Вопрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=6)}"
        )
        return system_prompt, user_prompt

    def build_context_prompt(self, user_query: str, documents: list[Document], recent_messages) -> tuple[str, str]:
        previous_messages = recent_messages[:-1]
        last_user = self.find_last_meaningful_user_message(previous_messages)
        last_assistant = self.find_last_assistant_message(previous_messages)

        system_prompt = (
            "Ты дружелюбный помощник по колледжам Москвы. "
            "Пользователь задаёт уточняющий вопрос в продолжение прошлого диалога. "
            "Отвечай только на русском языке. Никаких китайских, японских или английских вставок. "
            "Не выдумывай факты о колледжах, сроках, работодателях, практике, репутации или правилах приёма. "
            "Опирайся на прошлую тему, прошлый ответ и факты из базы. "
            "Если точных данных нет, честно скажи это и предложи, как проверить. "
            "Ответ должен быть коротким и полезным: до 1200 символов."
        )
        user_prompt = (
            f"Предыдущая тема пользователя:\n{last_user}\n\n"
            f"Предыдущий ответ ассистента:\n{last_assistant}\n\n"
            f"Текущий уточняющий вопрос:\n{user_query}\n\n"
            f"Факты из базы по теме:\n{self.compact_docs(documents, limit=5)}"
        )
        return system_prompt, user_prompt

    def try_llm_answer(self, mode: str, user_query: str, documents: list[Document], recent_messages) -> str:
        try:
            if mode == "recommend":
                system_prompt, user_prompt = self.build_recommend_prompt(user_query, documents)
            elif mode == "detail":
                system_prompt, user_prompt = self.build_detail_prompt(user_query, documents)
            elif mode == "faq":
                system_prompt, user_prompt = self.build_faq_prompt(user_query, documents)
            elif mode == "context":
                system_prompt, user_prompt = self.build_context_prompt(user_query, documents, recent_messages)
            elif mode == "faq_simple":
                result = self.render_simple_explanation(recent_messages)
                result = self.clean_llm_output(result)
                if result and not self.contains_cjk(result):
                    return result
                return "Проще говоря: я могу объяснить прошлый ответ, но без точных данных лучше уточни, какой именно момент непонятен."
            else:
                return self.render_clarify()

            result = self.call_llm(system_prompt, user_prompt)
            result = self.clean_llm_output(result)
            if result and len(result.strip()) >= 40 and not self.contains_cjk(result):
                return result.strip()

            logger.warning("LLM output rejected: empty/short/CJK")
        except Exception as e:
            logger.warning(f"LLM answer failed: {e}")

        if mode == "recommend":
            return self.render_recommendation_fallback(documents, user_query)
        if mode == "detail":
            return self.render_detail_fallback(documents)
        if mode == "faq":
            return self.render_faq_fallback(documents)
        if mode == "context":
            return self.render_context_fallback(user_query, documents, recent_messages)
        if mode == "faq_simple":
            return self.render_simple_explanation(recent_messages)
        return self.render_clarify()

    def render_context_fallback(self, user_query: str, documents: list[Document], recent_messages) -> str:
        previous_messages = recent_messages[:-1]
        last_user = self.find_last_meaningful_user_message(previous_messages)
        last_assistant = self.find_last_assistant_message(previous_messages)

        if self.is_general_explain_followup(user_query) or self.is_followup_for_simplify(user_query):
            if last_assistant:
                return (
                    "Проще: смотри на специальность, профессии после обучения и то, насколько тебе близки реальные задачи. "
                    "Если направление кажется интересным, следующий шаг — сравнить 2–3 колледжа и посмотреть их условия поступления."
                )

        specialty_docs = [doc for doc in documents if doc.doc_type == "specialty"][:3]
        if specialty_docs:
            lines = ["Если продолжать прошлую тему, я бы смотрел на это так:"]
            for doc in specialty_docs:
                college = self.extract_college_name(doc)
                spec = self.extract_specialty_name(doc)
                professions = doc.metadata_json.get("professions", [])
                if college and spec:
                    line = f"- {college}: {spec}"
                    if professions:
                        line += f" → после обучения: {', '.join(professions[:3])}"
                    lines.append(line)
            lines.append("Чтобы понять, подходит ли направление, сравни не только колледжи, но и будущие профессии: чем люди реально занимаются после обучения.")
            return "\n".join(lines)

        if last_user:
            return (
                f"Я понял это как продолжение темы: «{last_user}». "
                "Но в базе не хватает точных фактов для уверенного ответа. Лучше уточни: хочешь узнать про профессии после обучения, поступление или конкретный колледж?"
            )

        return self.render_clarify()

    def render_clarify(self) -> str:
        return (
            "Понял. Давай чуть сузим запрос.\n\n"
            "Напиши, что тебе ближе: разработка, аналитика, безопасность, дизайн, право, финансы, транспорт или что-то ещё.\n"
            "Если уже смотришь конкретный колледж, можешь просто написать его название."
        )

    def save_and_return(
        self,
        db: Session,
        session,
        user_query: str,
        answer: str,
        dialog_mode: str,
    ) -> dict[str, str]:
        self.session_service.add_message(db=db, session=session, role="user", content=user_query)
        self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
        return {
            "session_id": session.session_id,
            "answer": answer,
            "dialog_mode": dialog_mode,
        }


    def is_source_question(self, text: str) -> bool:
        q = self.normalize_text(text).replace("ё", "е")
        return any(x in q for x in [
            "откуда ты это знаешь",
            "откуда знаешь",
            "откуда твоя база",
            "откуда база",
            "база данных ответов",
            "откуда информация",
            "откуда инфа",
            "источник информации",
        ])

    def pick_script_answer(self, decision: RouterDecision, user_query: str) -> str:
        script_type = decision.script_type or "default"
        variants: dict[str, list[str]] = {
            "greeting": [
                "Привет. Я помогу подобрать колледж, специальность или ответить на вопросы про поступление в Москве. Напиши, что тебе интересно.",
                "Привет! Можешь спросить про колледж, профессию, поступление, документы или просто написать, кем хочешь стать.",
                "Привет. Я помощник по колледжам Москвы. Давай разберёмся, какое направление тебе подойдёт.",
            ],
            "intro": [
                "Я помощник по колледжам Москвы. Помогаю выбрать направление, подобрать колледжи и объяснить вопросы про поступление.",
                "Меня можно воспринимать как тестового консультанта по колледжам Москвы: подбираю варианты, объясняю специальности и отвечаю по базе.",
            ],
            "creator": [
                "Я тестовый помощник, которого сделали для подбора колледжей Москвы и проверки RAG-ответов на реальных диалогах.",
                "Я локальный помощник проекта по колледжам Москвы. Моя задача — отвечать по базе, а не рассказывать личные истории.",
            ],
            "attention": [
                "Я на связи. Напиши вопрос про колледжи, специальности или поступление — и разберём.",
                "Слышу тебя. Давай лучше по делу: хочешь подобрать направление или узнать про конкретный колледж?",
            ],
            "rating": [
                "Я не могу честно оценивать колледжи по десятибалльной шкале без понятных критериев. Зато могу сравнить 2–3 колледжа по специальностям, профессиям после обучения, адресам и контактам.",
                "Оценку ‘из 10’ я лучше не буду выдумывать. Могу помочь сравнить колледжи по конкретному направлению: например, IT, педагогика, дизайн, право или логистика.",
            ],
            "favorite": [
                "У меня нет любимого колледжа или мема. Я лучше подберу вариант под твои интересы и факты из базы.",
                "Я не выбираю любимчиков просто так. Но могу объяснить, какой колледж сильнее подходит под конкретную цель.",
            ],
            "source": [
                "Я беру ответ из локальной базы колледжей и FAQ проекта. Если в базе нет факта, я должен прямо сказать, что не знаю, и предложить проверить сайт колледжа или приёмную комиссию.",
                "Основа ответа — документы из базы проекта. Там есть колледжи, специальности, профессии после обучения, адреса и часть FAQ. То, чего нет в базе, лучше уточнять на сайте колледжа или в приёмной комиссии.",
            ],
            "abuse": [
                "Давай без оскорблений. Я могу помочь с колледжами Москвы, специальностями и поступлением.",
                "Понимаю, что ответ мог раздражать, но ругань не поможет. Напиши, что именно нужно исправить: колледж, направление или вопрос по поступлению.",
                "Окей, сбавим градус. Задай нормальный вопрос — и я попробую ответить точнее.",
            ],
            "nonsense": [
                "Не понял запрос. Напиши обычным текстом: например, ‘куда пойти на IT’, ‘какие документы нужны’ или ‘расскажи про КАИТ 20’.",
                "Похоже, сообщение случайное. Спроси про колледж, профессию или поступление — я помогу.",
            ],
            "default": [
                "Я могу помочь с колледжами Москвы, специальностями и поступлением. Напиши вопрос чуть конкретнее.",
            ],
        }
        return random.choice(variants.get(script_type, variants["default"]))

    def render_out_of_scope(self, user_query: str) -> str:
        q = self.normalize_text(user_query)
        if "рецепт" in q or "кофе" in q:
            return (
                "Я не кулинарный бот и не буду придумывать рецепт. "
                "Но если тебе интересна готовка как профессия, могу подсказать колледжи с направлением ‘Поварское и кондитерское дело’."
            )
        if "теорем" in q or "алгоритм" in q or "код" in q or "задач" in q:
            return (
                "Я здесь именно как помощник по колледжам Москвы и поступлению. "
                "Учебные задачи, теоремы и код лучше разбирать отдельно.\n\n"
                "Если хочешь связать это с выбором профессии, могу подсказать, где учиться на программиста, инженера или аналитика."
            )
        return (
            "Это не совсем моя тема. Я лучше всего помогаю с колледжами Москвы, специальностями и поступлением.\n\n"
            "Можешь спросить: ‘куда поступать на логиста’, ‘расскажи про МПК’ или ‘какие документы нужны’."
        )

    def compact_history_text(self, messages, limit: int = 8) -> str:
        chunks: list[str] = []
        for msg in messages[-limit:]:
            role = getattr(msg, "role", "")
            content = re.sub(r"\s+", " ", str(getattr(msg, "content", "")).strip())
            if content:
                chunks.append(f"{role}: {content[:500]}")
        return "\n".join(chunks) or "Истории нет."

    def render_chat_answer(self, decision: RouterDecision, recent_messages) -> str:
        system_prompt = (
            "Ты коротко отвечаешь как помощник по колледжам Москвы. "
            "Это режим обычной болталки или реакции пользователя. Не подбирай колледжи, если пользователь прямо не просит. "
            "Не выдумывай факты. Отвечай только на русском. Максимум 3 предложения. "
            "Мягко возвращай разговор к колледжам, специальностям или поступлению."
        )
        user_prompt = (
            f"История:\n{self.compact_history_text(recent_messages)}\n\n"
            f"Сообщение пользователя:\n{decision.normalized_query}"
        )
        try:
            result = self.clean_llm_output(self.call_llm(system_prompt, user_prompt))
            if result and len(result) >= 10 and not self.contains_cjk(result):
                return result
        except Exception as e:
            logger.warning(f"chat answer failed: {e}")
        return "Я на связи. Лучше всего я помогаю с колледжами Москвы, специальностями и поступлением. Напиши, что хочешь узнать."

    def render_career_guidance_answer(self, decision: RouterDecision, recent_messages) -> str:
        q = self.normalize_text(decision.normalized_query).replace("ё", "е")
        history = self.compact_history_text(recent_messages, limit=8).lower()
        full = f"{history}\n{q}"

        # Жёсткие профориентационные сценарии без LLM, чтобы не повторять старые шаблоны.
        if any(x in full for x in ["дет", "помощ", "овз", "пенсион", "люд", "общаться"]):
            return (
                "По тому, что ты описываешь, тебе ближе направление ‘люди и помощь’, а не IT.\n\n"
                "Я бы смотрел такие варианты:\n"
                "1. Педагогика — если хочешь работать с детьми: начальные классы, дошкольное образование, вожатство.\n"
                "2. Социальная работа — если интересна помощь людям, сопровождение, реабилитация, поддержка семей и пожилых.\n"
                "3. Адаптивная физическая культура / социальные профессии — если хочется помогать людям с ОВЗ через занятия, сопровождение или восстановление.\n\n"
                "Следующий шаг: могу подобрать колледжи по педагогике или социальной работе и показать, какие профессии указаны после обучения."
            )

        if any(x in full for x in ["рисован", "живоп", "картин", "творч", "литератур"]):
            return (
                "Если тебе важно именно рисование, а не графический дизайн, я бы смотрел художественные направления.\n\n"
                "Ближе всего по базе:\n"
                "1. Живопись (по видам) — если хочешь развивать именно художественные навыки.\n"
                "2. Декоративно-прикладное искусство и народные промыслы — если нравится ручная работа, материалы, предметы и оформление.\n"
                "3. Художник по костюму — если интересны образы, одежда, сцена, театр или кино.\n\n"
                "Могу дальше подобрать колледжи, где есть живопись, или рассказать про конкретный колледж."
            )

        if any(x in full for x in ["матем", "информ", "физ", "игр", "cs", "айти", "it", "код", "программ"]):
            return (
                "Если тебе нравятся математика, информатика и игры, это хороший вход в IT. То, что ты пока не умеешь кодить, нормально: колледж как раз даёт базу.\n\n"
                "Я бы смотрел 3 направления:\n"
                "1. Разработка и управление программным обеспечением (Программист) — если хочешь учиться писать код, делать сайты/приложения и работать с базами данных.\n"
                "2. Сетевое и системное администрирование — если больше интересны компьютеры, сети, серверы и настройка систем.\n"
                "3. Обеспечение информационной безопасности — если цепляет защита систем, уязвимости и кибербезопасность.\n\n"
                "Хочешь — расскажу подробнее про специальность ‘Программист’ или сразу подберу колледжи под IT."
            )

        # Если жёсткого сценария нет — короткий LLM, но без колледжей.
        system_prompt = (
            "Ты дружелюбный профориентационный помощник по колледжам Москвы. "
            "Пользователь пока выбирает направление. Не перечисляй случайные колледжи. "
            "Сначала отрази его интересы, затем предложи 2-3 направления и один следующий шаг. "
            "Не выдумывай факты о колледжах. Отвечай только на русском, коротко."
        )
        user_prompt = (
            f"История:\n{self.compact_history_text(recent_messages)}\n\n"
            f"Запрос пользователя:\n{decision.normalized_query}"
        )
        try:
            result = self.clean_llm_output(self.call_llm(system_prompt, user_prompt))
            if result and len(result) >= 30 and not self.contains_cjk(result):
                return result
        except Exception as e:
            logger.warning(f"career guidance failed: {e}")
        return (
            "Нормально не знать, кем хочешь быть. Давай сузим выбор: тебе ближе люди, техника, творчество, спорт, право, деньги или компьютеры?\n\n"
            "Ответь 1–2 словами, и я предложу несколько направлений без случайных колледжей."
        )

    def map_router_mode_to_answer_mode(self, decision: RouterDecision) -> str:
        mapping = {
            "recommend_colleges": "recommend",
            "faq": "faq",
            "detail": "detail",
            "detail_more": "detail",
            "career_guidance": "career_guidance",
            "chat": "chat",
            "script": "script",
            "out_of_scope": "clarify",
        }
        return mapping.get(decision.mode, "clarify")

    def ask(
        self,
        db: Session,
        user_id: str,
        user_query: str,
        session_id: str | None = None,
        top_k: int = 5,
    ) -> dict[str, str]:
        logger.info(f"Новый вопрос пользователя: {user_query}")

        session = self.session_service.get_or_create_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
        )

        previous_messages = self.get_recent_messages_safe(db=db, session=session, limit=24)

        # Источник данных — скриптовый вопрос, не должен уходить в retriever.
        if self.is_source_question(user_query):
            decision = RouterDecision(
                mode="script",
                normalized_query=user_query,
                script_type="source",
                needs_retrieval=False,
                confidence=1.0,
                reason="source_question_guard",
            )
            answer = self.pick_script_answer(decision, user_query)
            return self.save_and_return(db, session, user_query, answer, "script")

        decision = self.dialog_router.route(user_query=user_query, history_messages=previous_messages)
        logger.info(
            "Router decision: mode=%s college=%s topic=%s confidence=%.2f reason=%s normalized=%s",
            decision.mode,
            decision.college,
            decision.topic,
            decision.confidence,
            decision.reason,
            decision.normalized_query,
        )

        # Жёсткие сценарии до retrieval и до генерации большого ответа.
        if decision.mode == "script":
            answer = self.pick_script_answer(decision, user_query)
            return self.save_and_return(db, session, user_query, answer, "script")

        if decision.mode == "out_of_scope":
            answer = self.render_out_of_scope(user_query)
            return self.save_and_return(db, session, user_query, answer, "out_of_scope")

        if self.is_college_count_query(user_query):
            count = self.get_colleges_count(db)
            answer = f"По моей базе сейчас {count} колледжей Москвы."
            return self.save_and_return(db, session, user_query, answer, "faq")

        # Детерминированный ответ на "все специальности колледжа" — без Qwen и без retriever.
        requested_college = self.canonical_college_from_text(user_query) or decision.college
        if requested_college and self.is_all_specialties_request(user_query):
            answer = self.render_all_specialties_for_college(db, requested_college)
            return self.save_and_return(db, session, user_query, answer, "detail_more")

        # Детерминированный ответ на "третью/вторую специальность" из прошлого списка.
        ordinal = self.extract_ordinal_request(user_query)
        if ordinal is not None:
            college_from_list, specs = self.parse_last_numbered_specialties(previous_messages)
            if 1 <= ordinal <= len(specs):
                answer = self.render_specialty_detail_by_name(db, specs[ordinal - 1], college_from_list)
                return self.save_and_return(db, session, user_query, answer, "detail_more")

        # Исправление после ошибки: "при чём тут юриспруденция/веб-разработка".
        if any(mark in self.normalize_text(user_query) for mark in ["при чем тут", "при чём тут", "не то", "не об этом"]):
            last_college = self.canonical_college_from_text(self.find_last_assistant_message(previous_messages)) or self.canonical_college_from_text(self.find_last_user_message(previous_messages))
            if last_college:
                answer = self.render_all_specialties_for_college(db, last_college)
                return self.save_and_return(db, session, user_query, answer, "detail_more")
            answer = "Да, ты прав — я съехал не в ту тему. Напиши колледж или специальность ещё раз, и я отвечу строго по базе."
            return self.save_and_return(db, session, user_query, answer, "script")

        if decision.mode == "chat":
            answer = self.render_chat_answer(decision, previous_messages)
            return self.save_and_return(db, session, user_query, answer, "chat")

        if decision.mode == "career_guidance":
            answer = self.render_career_guidance_answer(decision, previous_messages)
            return self.save_and_return(db, session, user_query, answer, "career_guidance")

        # Дальше идут режимы, которым нужны факты из базы.
        self.session_service.add_message(db=db, session=session, role="user", content=user_query)
        recent_messages = self.get_recent_messages_safe(db=db, session=session, limit=24)

        retrieval_query = decision.normalized_query or self.build_retrieval_query(user_query, recent_messages)

        answer_mode = self.map_router_mode_to_answer_mode(decision)
        diversify = answer_mode == "recommend"
        if answer_mode in {"detail", "faq", "context"}:
            diversify = False

        search_top_k = top_k
        if decision.mode in {"detail", "detail_more"}:
            search_top_k = max(top_k, 8)
        if decision.mode == "faq":
            search_top_k = max(top_k, 6)

        documents = self.retriever.search(
            db=db,
            query=retrieval_query,
            top_k=search_top_k,
            diversify_by_college=diversify,
        )

        # Вопросы про ОВЗ/инвалидность лучше отвечать устойчивым официальным шаблоном.
        q_norm = self.normalize_text(user_query)
        if decision.mode == "faq" and any(x in q_norm for x in ["овз", "инвалид", "вступитель", "не могу сдавать", "как все"]):
            answer = self.render_ovz_faq_answer(q_norm)
            self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
            return {"session_id": session.session_id, "answer": answer, "dialog_mode": "faq"}

        if self.is_duration_query(user_query):
            answer = self.render_no_duration_data(user_query, documents)
            self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
            return {
                "session_id": session.session_id,
                "answer": answer,
                "dialog_mode": "faq",
            }

        # Для detail_more заставляем генератор раскрывать прошлую тему, а не подбирать новые колледжи.
        if decision.mode == "detail_more":
            answer_mode = "detail"

        answer = self.try_llm_answer(answer_mode, user_query, documents, recent_messages)

        self.session_service.add_message(db=db, session=session, role="assistant", content=answer)

        return {
            "session_id": session.session_id,
            "answer": answer,
            "dialog_mode": decision.mode,
        }
