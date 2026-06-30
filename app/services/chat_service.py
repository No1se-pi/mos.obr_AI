import random
import re
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.repository import Document
from app.logger import get_logger
from app.rag.retriever import Retriever
from app.services.session_service import SessionService
from app.llm.ollama_client import OllamaClient
from app.services.dialog_router import DialogRouter, RouterDecision
from app.services.reference_catalog import ReferenceCatalog

logger = get_logger(__name__)

ATLAS_URL = "https://colleges.shkolamoskva.ru/atlas"
COLLEGE_EDUCATION_BLOG_URL = "https://colleges.shkolamoskva.ru/blog/kolledzh-jeto-kakoe-obrazovanie"
GENERAL_ADMISSION_SUPPORT_URL = "https://colleges.shkolamoskva.ru/contacts"
GENERAL_ADMISSION_SUPPORT_EMAIL = "Spo@edu.mos.ru"
GENERAL_ADMISSION_SUPPORT_PHONE = "8 495 568 00 88"

LLM_ERROR_MARKERS = {
    "ошибка при обращении к модели",
    "ollama error",
    "connection refused",
    "failed to connect",
    "read timed out",
    "timeout",
}


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
    "отсроч",
    "отстроч",
    "армия",
    "арм",
    "призыв",
    "военком",
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
    "учебник",
    "учебники",
    "дод",
    "день открытых дверей",
    "открытых дверей",
    "приоритет",
    "первоочеред",
    "преимуществ",
    "сво",
    "мобилиз",
    "военнослуж",
    "добровол",
    "контрактник",
    "олимпиад",
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
    "расскажи больше",
    "побольше",
    "больше деталей",
    "подробнее про это",
    "расскажи подробнее про это",
}

FOLLOWUP_CONFIRM_MARKERS = {
    "ок",
    "хорошо",
    "да",
    "ага",
    "давай",
}

OTHER_COLLEGE_MARKERS = {
    "другие колледжи",
    "другие варианты",
    "еще колледжи",
    "ещё колледжи",
    "еще варианты",
    "ещё варианты",
    "какие еще",
    "какие ещё",
    "покажи еще",
    "покажи ещё",
    "еще",
    "ещё",
    "больше вариантов",
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

CONTACT_HINTS = {
    "адрес",
    "адреса",
    "адресу",
    "контакт",
    "контакты",
    "телефон",
    "номер",
    "почта",
    "email",
    "e-mail",
    "сайт",
    "адрес сайта",
    "приемная",
    "приёмная",
    "vk",
    "тг",
    "telegram",
}

ADDRESS_HINTS = {
    "адрес",
    "адреса",
    "адресу",
    "адрес отделения",
    "адрес корпуса",
    "по какому адресу",
    "какой адрес",
    "где находится",
    "где расположен",
    "где расположено",
    "где располагается",
    "как добраться",
    "куда ехать",
    "местонахождение",
}

COMPARISON_HINTS = {
    "сравни",
    "сравнить",
    "сравнение",
    "чем отличается",
    "чем отличаются",
    "кто лучше",
    "что лучше",
    "лучше в рейтинге",
    "рейтинг",
}

STAFF_HINTS = {
    "директор",
    "руководитель",
    "заведующий",
    "заместитель",
    "кто возглавляет",
}

GENERAL_SUPPORT_HINTS = {
    "общий номер",
    "общий телефон",
    "общие контакты",
    "общая приемная",
    "общая приёмная",
    "номер приемной",
    "номер приёмной",
    "телефон приемной",
    "телефон приёмной",
    "контакты приемной",
    "контакты приёмной",
    "приемная комиссия общая",
    "приёмная комиссия общая",
    "приемная кампания",
    "приёмная кампания",
    "приемная компания",
    "приёмная компания",
    "номер приемной кампании",
    "номер приёмной кампании",
    "номер приемной компании",
    "номер приёмной компании",
    "информационная поддержка",
    "поддержка колледжей москвы",
    "куда звонить",
    "куда писать",
}

INDUSTRY_PROFESSION_HINTS = {
    "какие профессии",
    "профессии в",
    "профессии по",
    "профессии отрасли",
    "отрасль",
    "отрасли",
    "сфера",
    "сфере",
    "перечисли колледжи отрасли",
    "колледжи отрасли",
    "креативная индустрия",
    "здравоохранение",
    "промышленность",
    "кем можно работать",
    "кем работают",
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
    "кигм 23": "Колледж индустрии гостеприимства и менеджмента № 23",
    "кигм23": "Колледж индустрии гостеприимства и менеджмента № 23",
    "кигим23": "Колледж индустрии гостеприимства и менеджмента № 23",
    "кп 11": "Колледж предпринимательства № 11",
    "кп11": "Колледж предпринимательства № 11",
    "тк 24": "Технологический колледж № 24",
    "тк24": "Технологический колледж № 24",
    "тпск максимчука": "Технический пожарно-спасательный колледж имени Героя Российской Федерации В.М. Максимчука",
    "максимчука": "Технический пожарно-спасательный колледж имени Героя Российской Федерации В.М. Максимчука",
    "кмт": "Колледж музыкально-театрального искусства имени Г. П. Вишневской",
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
        self.reference_catalog = ReferenceCatalog()

    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s№.-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def compact_key(self, text: str) -> str:
        """Сопоставляет школьные сокращения вроде "кп11" с alias "КП 11"."""
        normalized = self.normalize_text(text).replace("ё", "е")
        return re.sub(r"[^а-яa-z0-9№]", "", normalized)

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

    def is_more_colleges_request(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        return any(marker.replace("ё", "е") in q for marker in OTHER_COLLEGE_MARKERS)

    def is_compare_colleges_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        return any(marker in q for marker in COMPARISON_HINTS)

    def is_staff_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        return any(marker in q for marker in STAFF_HINTS)

    def is_general_support_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        if any(marker in q for marker in GENERAL_SUPPORT_HINTS):
            return True
        has_admission = any(marker in q for marker in ["приемн", "приемк", "приемная", "приемной", "комисси", "кампан", "компан"])
        has_contact = any(marker in q for marker in ["номер", "телефон", "контакт", "почт", "email", "куда звон", "куда пис"])
        has_specific_college = self.canonical_college_from_text(user_query) is not None
        return has_admission and has_contact and not has_specific_college

    def is_catalog_recommendation_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        markers = {
            "где учат",
            "где обуч",
            "учат на",
            "обучиться на",
            "колледжи для",
            "колледж для",
            "какие есть колледжи",
            "в каком колледже",
            "в каких колледжах",
            "профессия",
            "профессии",
            "кем работать",
            "кем можно работать",
            "хочу поступить по",
            "хочу поступить на",
            "направления обучения",
            "связанные с",
        }
        return any(marker in q for marker in markers)

    def is_college_existence_question(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        has_college_hint = "колледж" in q or "такой" in q or "он" in q
        has_existence_hint = any(marker in q for marker in ["точно есть", "существует", "реально есть", "правда есть"])
        return has_college_hint and has_existence_hint

    def get_reference_catalog(self) -> ReferenceCatalog:
        catalog = getattr(self, "reference_catalog", None)
        if catalog is None:
            catalog = ReferenceCatalog()
            self.reference_catalog = catalog
        return catalog

    def is_contact_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        return any(marker in q for marker in CONTACT_HINTS) or self.is_address_query(user_query)

    def is_address_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        return any(marker in q for marker in ADDRESS_HINTS)

    def is_industry_professions_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        if not any(marker in q for marker in INDUSTRY_PROFESSION_HINTS):
            return False
        return self.get_reference_catalog().match_industry(user_query) is not None

    def is_industry_colleges_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        has_college = "колледж" in q or "колледжи" in q or "где уч" in q or "поступить" in q
        has_industry = self.get_reference_catalog().match_industry(user_query) is not None
        return has_college and has_industry


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

    def is_llm_error_output(self, text: str) -> bool:
        normalized = self.normalize_text(text)
        return any(marker in normalized for marker in LLM_ERROR_MARKERS)

    def clean_llm_output(self, text: str) -> str:
        if self.is_llm_error_output(text):
            return ""

        # Если модель внезапно ушла в китайский/японский/корейский, режем ответ до первого такого символа.
        # Если после обрезки получается слишком мало смысла — включится fallback.
        match = CJK_RE.search(text)
        if match:
            text = text[: match.start()].strip()

        text = re.sub(r"#+\s*", "", text)
        text = text.replace("Коллеги,", "")
        text = text.replace("коллеги,", "")
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"<(https?://[^>\s]+)>", r"\1", text)
        text = re.sub(r"https?://\S*\.\.\.", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if self.is_llm_error_output(text):
            return ""
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
                f"{self.verification_hint()} "
                "Если хочешь, я могу подсказать, какие колледжи смотреть по этой специальности."
            )

        return (
            "Я могу ошибаться со сроком обучения по этому направлению. "
            f"{self.verification_hint()}"
        )

    def render_college_contacts(self, db: Session, college_name: str, user_query: str) -> str:
        college_card = self.get_college_card_for_name(db, college_name)
        if not college_card:
            return (
                f"По колледжу «{college_name}» я могу ошибаться с контактами. "
                f"{self.verification_hint()}"
            )

        display_name = self.extract_college_name(college_card) or college_name
        metadata = college_card.metadata_json
        website = str(metadata.get("website") or metadata.get("site") or "").strip()
        contacts = [str(item).strip() for item in metadata.get("contacts", []) if str(item).strip()]
        addresses = [str(item).strip() for item in metadata.get("addresses", []) if str(item).strip()]

        q = self.normalize_text(user_query).replace("ё", "е")
        wants_site = "сайт" in q or "адрес сайта" in q
        wants_address = self.is_address_query(user_query) and not wants_site
        wants_contacts = any(marker in q for marker in ["контакт", "телефон", "номер", "почта", "email", "e-mail", "приемная", "приёмная"])
        include_all = not (wants_site or wants_address or wants_contacts)

        lines = [f"{display_name}: контакты из моей базы."]
        if website and (include_all or wants_site or wants_contacts):
            lines.append(f"Сайт: {website}")

        if contacts and (include_all or wants_contacts):
            phones = [item for item in contacts if re.search(r"\d", item) and not item.startswith("http") and "@" not in item]
            emails = [item for item in contacts if "@" in item and not item.startswith("http")]
            links = [item for item in contacts if item.startswith("http")]
            other = [item for item in contacts if item not in phones and item not in emails and item not in links]

            if phones:
                lines.append(f"Телефон: {'; '.join(phones)}")
            if emails:
                lines.append(f"Почта: {'; '.join(emails)}")
            if links:
                lines.append(f"Соцсети/каналы: {'; '.join(links)}")
            if other:
                lines.append(f"Дополнительно: {'; '.join(other)}")

        if addresses and (include_all or wants_address):
            lines.append("Адреса:")
            for address in addresses[:6]:
                lines.append(f"- {address}")

        if len(lines) == 1:
            lines.append("Точных контактов в моей базе не нашёл.")

        lines.append("")
        lines.append(self.verification_hint(website or None))
        return "\n".join(lines)

    def render_general_admission_support(self) -> str:
        return (
            "Для общих вопросов по приёму в колледжи Москвы можно обратиться в информационную поддержку:\n"
            f"Телефон: {GENERAL_ADMISSION_SUPPORT_PHONE}\n"
            f"Почта: {GENERAL_ADMISSION_SUPPORT_EMAIL}\n"
            f"Страница контактов: {GENERAL_ADMISSION_SUPPORT_URL}\n\n"
            "По конкретному колледжу лучше дополнительно смотреть его сайт и приёмную комиссию."
        )

    def render_staff_unknown_answer(self, db: Session, user_query: str) -> str:
        college = self.canonical_college_from_db(db, user_query) or self.canonical_college_from_text(user_query)
        if college:
            card = self.get_college_card_for_name(db, college)
            website = card.metadata_json.get("website", "") if card else ""
            return (
                f"По «{college}» я не буду выдумывать директора или состав администрации: в моей базе это не хранится.\n\n"
                f"{self.verification_hint(website or None)}"
            )
        return (
            "Я не храню данные о директорах и сотрудниках колледжей, поэтому не буду угадывать. "
            f"Лучше проверить официальный сайт колледжа или страницу контактов: {GENERAL_ADMISSION_SUPPORT_URL}."
        )

    def catalog_query_variants(self, user_query: str) -> list[str]:
        q = self.normalize_text(user_query).replace("ё", "е")
        variants = [user_query]
        replacements = [
            ("повор", "повар"),
            ("юриспруденц", "юрист право"),
            ("хакинг", "легальная кибербезопасность информационная безопасность сети программирование"),
            ("хакер", "легальная кибербезопасность информационная безопасность сети программирование"),
            ("пентест", "легальная кибербезопасность информационная безопасность сети программирование"),
            ("кибербез", "информационная безопасность сети программирование"),
            ("ювелир", "ювелир-закрепщик ювелир-монтировщик ювелир-огранщик природных камней технология обработки алмазов"),
            ("украшен", "ювелир ювелирное дело декоративно-прикладное искусство технология обработки алмазов"),
            ("драгоцен", "ювелир ювелирное дело технология обработки алмазов"),
            ("кольц", "ювелир ювелирное дело"),
            ("серьг", "ювелир ювелирное дело"),
            ("нейросет", "интеллектуальные интегрированные системы разработчик интеллектуальных систем IT"),
            ("искусственн интеллект", "интеллектуальные интегрированные системы разработчик интеллектуальных систем IT"),
            ("креативн", "дизайн креативные индустрии"),
            ("здравоохран", "медицина здоровье"),
            ("промышлен", "производство инженерия промышленное оборудование мехатроника сварщик"),
        ]
        for needle, replacement in replacements:
            if needle in q:
                variants.append(f"{user_query}. {replacement}")
        return variants

    def render_catalog_recommendation(
        self,
        user_query: str,
        *,
        skip_colleges: set[str] | None = None,
        is_more_request: bool = False,
    ) -> str | None:
        for query in self.catalog_query_variants(user_query):
            answer = (
                self.render_profession_recommendations_from_catalog(
                    query,
                    skip_colleges=skip_colleges,
                    is_more_request=is_more_request,
                )
                or self.render_industry_college_recommendations_from_catalog(
                    query,
                    skip_colleges=skip_colleges,
                    is_more_request=is_more_request,
                )
            )
            if answer:
                return answer
        return None

    def render_common_faq_answer(self, user_query: str) -> str | None:
        q = self.normalize_text(user_query).replace("ё", "е")
        support = f"{GENERAL_ADMISSION_SUPPORT_PHONE}, {GENERAL_ADMISSION_SUPPORT_EMAIL}"

        if self.is_general_support_query(user_query):
            return self.render_general_admission_support()

        if "учебник" in q:
            return (
                "По FAQ проекта учебно-методическая литература предоставляется. "
                "Если речь про дополнительные материалы, рабочую форму или платные расходники, это лучше уточнить в выбранном колледже.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if "общежит" in q:
            return (
                "По FAQ проекта в колледжах Правительства Москвы нет общежитий. "
                "Вопрос с жильём нужно решать самостоятельно.\n\n"
                f"Если ситуация нестандартная, лучше уточнить в колледже или через общую поддержку: {support}."
            )

        if any(x in q for x in ["мама", "папа", "родител"]) and "заяв" in q:
            return (
                "По FAQ проекта заявление на поступление подаёт сам абитуриент из своего личного кабинета на mos.ru. "
                "Родитель не подаёт заявление со своего личного кабинета.\n\n"
                f"Если есть техническая проблема с доступом, можно уточнить порядок через поддержку: {support}."
            )

        if "документ" in q and any(x in q for x in ["какие", "нужн", "поступ", "пода", "расскажи", "список"]):
            return (
                "Для поступления обычно нужны сведения о поступающем, документе личности, СНИЛС и образовании. "
                "Если данные не подтянулись в личном кабинете mos.ru, могут понадобиться скан-копии документа личности и документа об образовании.\n\n"
                "Если есть льгота, ОВЗ, инвалидность или индивидуальные достижения, подтверждающие документы прикладывают отдельно. "
                "Точный список лучше сверить в форме заявления на mos.ru и в приёмной комиссии выбранного колледжа.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if ("несколько" in q or "сколько" in q) and any(x in q for x in ["колледж", "заявлен", "вариант"]):
            return (
                "По базе вижу, что при подаче заявления на mos.ru вариантам присваивается приоритет от 1 до 5: "
                "1 — самый желанный вариант. Это значит, что выбор нескольких вариантов предусмотрен, но точные ограничения формы лучше проверить прямо на mos.ru.\n\n"
                f"Для уверенности можно обратиться в информационную поддержку: {support}."
            )

        if "бюджет" in q and any(x in q for x in ["мест", "сколько", "конкурс", "проход", "балл"]):
            return (
                "В моей базе нет точного количества бюджетных мест и проходных значений по всем колледжам и специальностям.\n\n"
                "Бюджет и конкурс зависят от конкретной программы, года приёма и колледжа. "
                "Лучше проверить страницу выбранного колледжа, Атлас профессий или уточнить в приёмной комиссии.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if any(x in q for x in ["последний день", "до какого", "когда можно подать", "срок подачи", "сроки подачи"]):
            return (
                "По FAQ проекта приём заявлений через mos.ru начинается 26 июня 2026 года.\n"
                "Для московских выпускников 9 класса 2025 и 2026 годов подача на бюджет завершается 26 июля 2026 года, "
                "а если нужны вступительные испытания — 20 июля 2026 года.\n"
                "Для остальных категорий граждан на базе 9 и 11 классов заявления можно подать до 15 августа 2026 года, "
                "а если есть вступительные испытания — до 10 августа 2026 года.\n\n"
                "Лучше сверить дату для своей ситуации на mos.ru или сайте колледжа."
            )

        if "приоритет" in q:
            return (
                "Приоритет в заявлении — это порядок твоих желаний по программам обучения.\n\n"
                "1 — самый важный и желанный вариант, 5 — менее приоритетный. "
                "При зачислении система учитывает конкурс и этот порядок: сначала смотрят более высокий приоритет, если по нему проходишь. "
                "Также могут учитываться баллы ГИА, первоочередное/преимущественное право, индивидуальные достижения и вступительные испытания, если они есть.\n\n"
                "Если выбираешь несколько вариантов, лучше ставить на 1 место не “самый надёжный”, а тот, куда больше всего хочешь поступить."
            )

        if any(x in q for x in ["день открытых", "открытых двер", "дод"]):
            return (
                "В базе нет точного расписания дней открытых дверей по каждому колледжу. "
                "Лучше уточнить дату на сайте выбранного колледжа, в Атласе профессий или через общую приёмную кампанию.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        has_ovz_context = any(x in q for x in ["овз", "инвалид", "особые услов", "специальные услов", "не могу"])
        has_general_exam = any(x in q for x in ["вступитель", "испытан", "внутренн", "ви ", "экзам"]) and not has_ovz_context
        if has_general_exam:
            return (
                "В моей базе нет полного перечня вступительных испытаний по всем колледжам и специальностям.\n\n"
                "Условия могут зависеть от конкретного колледжа и выбранной специальности. "
                "Я могу помочь подобрать колледж или специальность, а затем дать сайт и контакты приёмной комиссии, где лучше уточнить вступительные испытания.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if any(x in q for x in ["сво", "участник сво", "мобилиз", "военнослуж", "добровол", "контрактник", "вдова", "вдовец"]):
            return (
                "В базе есть информация о первоочередном праве зачисления для отдельных категорий.\n\n"
                "Кратко: первоочередное право может относиться к отдельным участникам СВО, военнослужащим, мобилизованным, добровольцам, "
                "некоторым членам их семей, а также другим категориям, указанным в ч. 5.1 ст. 71 Закона об образовании.\n\n"
                "Важно:\n"
                "- статус и категорию нужно подтверждать официальными документами\n"
                "- точный перечень документов лучше уточнить в приёмной комиссии колледжа\n"
                "- правила приёма нужно перепроверить для конкретного года и колледжа\n\n"
                "По одному сообщению нельзя точно определить, относится ли ситуация к этой категории. Лучше сверить статус и документы с приёмной комиссией колледжа.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if "олимпиад" in q and any(x in q for x in ["преимуществ", "льгот", "поступ", "зачисл"]):
            return (
                "В моей базе нет подтверждения, что участие в олимпиадах автоматически даёт преимущество при поступлении в колледж. "
                "Олимпиады могут относиться к индивидуальным достижениям только если это прямо указано в правилах приёма.\n\n"
                "Лучше уточнить эту часть в правилах приёма конкретного колледжа или в приёмной комиссии."
            )

        if "льгот" in q or "первоочеред" in q or "преимуществен" in q:
            return (
                "По FAQ проекта есть первоочередное и преимущественное право, а также учёт индивидуальных достижений при равных баллах. "
                "Но полный перечень категорий и документов лучше проверять по официальному правилу для твоей ситуации.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if "напрямую" in q and "заяв" in q:
            return (
                "По FAQ проекта поступление на бюджет оформляется через электронное заявление на mos.ru. "
                "Если речь про платное обучение или нестандартную ситуацию, лучше уточнить порядок у выбранного колледжа.\n\n"
                f"Общая информационная поддержка: {support}."
            )

        if "федеральн" in q and "правительств" in q:
            return (
                "Главное отличие не в уровне образования: и колледж, и техникум дают среднее профессиональное образование, то есть СПО.\n\n"
                "Колледжи Правительства Москвы относятся к московской системе колледжей, поэтому по поступлению лучше ориентироваться на mos.ru, "
                "Атлас профессий и правила приёма колледжей Москвы. Федеральные и частные колледжи тоже работают в системе СПО, "
                "но порядок приёма и отдельные условия они могут устанавливать самостоятельно.\n\n"
                f"Подробнее про то, что такое колледж и СПО: {COLLEGE_EDUCATION_BLOG_URL}\n"
                f"Для вопросов по московским колледжам: {support}."
            )

        if ("какое образование" in q or "что такое спо" in q or "что такое колледж" in q) and "колледж" in q:
            return (
                "Колледж — это среднее профессиональное образование, сокращённо СПО. "
                "Поступить можно после 9-го или 11-го класса. Обычно ЕГЭ для поступления в колледж не нужен, "
                "а дополнительные вступительные испытания бывают только на отдельных направлениях.\n\n"
                f"Подробнее можно почитать здесь: {COLLEGE_EDUCATION_BLOG_URL}"
            )

        return None

    def find_colleges_in_text(self, db: Session, text: str, limit: int = 5) -> list[str]:
        normalized = self.normalize_text(text).replace("ё", "е")
        compact = self.compact_key(text)
        found: list[str] = []
        seen: set[str] = set()

        def add(name: str) -> None:
            key = self.college_key(name)
            if name and key not in seen:
                seen.add(key)
                found.append(name)

        # Сначала известные alias, чтобы короткие школьные сокращения не терялись.
        for alias, canonical in sorted(KNOWN_COLLEGE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            alias_norm = self.normalize_text(alias).replace("ё", "е")
            alias_compact = self.compact_key(alias)
            if not alias_norm:
                continue
            if alias in {"мпк", "ммпк"}:
                if re.search(rf"(^|\s){re.escape(alias_norm)}($|\s)", normalized):
                    add(canonical)
                continue
            if alias_norm in normalized or (len(alias_compact) >= 3 and alias_compact in compact):
                add(canonical)

        docs = db.scalars(select(Document).where(Document.doc_type == "college")).all()
        variants: list[tuple[str, str]] = []
        for doc in docs:
            college_name = self.extract_college_name(doc)
            aliases = doc.metadata_json.get("aliases", []) or []
            for variant in [college_name, *[str(alias) for alias in aliases]]:
                variants.append((variant, college_name))

        for variant, college_name in sorted(variants, key=lambda item: len(item[0]), reverse=True):
            value = self.normalize_text(variant).replace("ё", "е")
            value_compact = self.compact_key(variant)
            if not value:
                continue
            if value in normalized:
                add(college_name)
            elif len(value_compact) >= 3 and value_compact in compact:
                add(college_name)
            if len(found) >= limit:
                break

        return found[:limit]

    def collect_seen_colleges_from_history(self, db: Session, messages) -> set[str]:
        seen: set[str] = set()
        for msg in messages:
            if getattr(msg, "role", "") != "assistant":
                continue
            for college in self.find_colleges_in_text(db, str(getattr(msg, "content", "") or ""), limit=20):
                seen.add(self.college_key(college))
        return seen

    def render_college_comparison(self, db: Session, user_query: str, previous_messages) -> str:
        colleges = self.find_colleges_in_text(db, user_query, limit=4)
        if len(colleges) < 2:
            history_college = self.find_last_college_in_history(db, previous_messages)
            if history_college and history_college not in colleges:
                colleges.append(history_college)

        if len(colleges) < 2:
            return (
                "Я могу сравнить колледжи, но мне нужны хотя бы два названия. "
                "Напиши, например: «сравни КС 54 и ИТ.Москва» или «сравни МПК и Ушинского»."
            )

        if "рейтинг" in self.normalize_text(user_query).replace("ё", "е"):
            intro = (
                "Объективный рейтинг я не буду выдумывать: в моей базе нет официальной шкалы «кто лучше». "
                "Зато сравню по тому, что есть в данных: специальности, профессии после обучения, адреса и сайты."
            )
        else:
            intro = "Сравню по фактам из моей базы: специальности, профессии после обучения, адреса и сайты."

        lines = [intro]
        for idx, college in enumerate(colleges[:3], start=1):
            card = self.get_college_card_for_name(db, college)
            display_name = self.extract_college_name(card) if card else college
            specs = self.get_all_specialty_docs_for_college(db, college)[:4]
            website = card.metadata_json.get("website", "") if card else ""
            addresses = card.metadata_json.get("addresses", []) if card else []

            lines.append("")
            lines.append(f"{idx}. {display_name}")
            if specs:
                spec_names = [self.extract_specialty_name(doc) for doc in specs if self.extract_specialty_name(doc)]
                lines.append(f"   Что смотреть: {', '.join(spec_names[:4])}.")
            if addresses:
                lines.append(f"   Адрес: {addresses[0]}")
            if website:
                lines.append(f"   Сайт: {website}")

        lines.append("")
        lines.append("Если скажешь направление сравнения — IT, педагогика, дизайн, медицина, право — я сравню точнее.")
        return "\n".join(lines)

    def render_detail_followup_from_history(self, db: Session, previous_messages) -> str | None:
        choices = self.parse_last_numbered_specialty_choices(previous_messages)
        if len(choices) > 1:
            lines = ["Могу рассказать подробнее, но в прошлом ответе было несколько вариантов. Выбери номер:"]
            for idx, (college, item) in enumerate(choices[:6], start=1):
                if college:
                    lines.append(f"{idx}. {college} — {item}")
                else:
                    lines.append(f"{idx}. {item}")
            return "\n".join(lines)

        if len(choices) == 1:
            college, item = choices[0]
            return self.render_specialty_detail_by_name(db, item, college)

        last_college = self.find_last_college_in_history(db, previous_messages)
        if last_college:
            return self.render_all_specialties_for_college(db, last_college)

        return None

    def render_industry_professions_from_catalog(self, user_query: str) -> str | None:
        match = self.get_reference_catalog().match_industry(user_query)
        if not match or not match.professions:
            return None

        professions = list(match.professions)
        if match.key == "medicine":
            professions.sort(key=self.medicine_profession_priority)
        professions = professions[:12]
        lines = [f"В отрасли «{match.title}» в моей базе есть такие профессии:"]
        for idx, profession in enumerate(professions, start=1):
            lines.append(f"{idx}. {profession}")

        if len(match.professions) > len(professions):
            lines.append(f"И ещё {len(match.professions) - len(professions)} профессий в этой отрасли.")

        lines.append("")
        lines.append("Если хочешь, я могу следующим сообщением подобрать колледжи по одной из этих профессий.")
        return "\n".join(lines)

    def render_profession_recommendations_from_catalog(
        self,
        user_query: str,
        *,
        skip_colleges: set[str] | None = None,
        is_more_request: bool = False,
    ) -> str | None:
        matches = self.get_reference_catalog().match_professions(user_query)
        if not matches:
            return None

        match = matches[0]
        skip_colleges = skip_colleges or set()
        lines: list[str] = []
        seen_colleges: set[str] = set()
        added = 0

        for entry in match.colleges:
            college_name = str(entry.get("college", "")).strip()
            specialty_name = str(entry.get("specialty", "")).strip()
            professions = [str(item).strip() for item in entry.get("professions", []) if str(item).strip()]
            college_key = self.college_key(college_name)
            if not college_name or not specialty_name or college_key in seen_colleges or college_key in skip_colleges:
                continue

            if added == 0:
                if is_more_request:
                    lines.append(f"Нашёл ещё варианты по профессии «{match.display_name}»:")
                else:
                    lines.append(f"По базе вижу такие варианты для профессии «{match.display_name}»:")

            lines.append(f"{added + 1}. {college_name} — {specialty_name}")
            if professions:
                lines.append(f"   После обучения: {', '.join(professions[:3])}")
            specialty_url = str(entry.get("specialty_url", "") or "").strip()
            if specialty_url:
                lines.append(f"   Подробнее о специальности: {specialty_url}")
            website = str(entry.get("website", "")).strip()
            if website:
                lines.append(f"   Сайт: {website}")

            seen_colleges.add(college_key)
            added += 1
            if added >= 3:
                break

        if added == 0:
            if is_more_request:
                return (
                    f"Пока не вижу ещё колледжей по профессии «{match.display_name}» среди справочника. "
                    f"{self.verification_hint()}"
                )
            return None

        lines.append("")
        lines.append("Если хочешь, могу показать ещё варианты или сравнить эти колледжи простыми словами.")
        return "\n".join(lines)

    def render_industry_college_recommendations_from_catalog(
        self,
        user_query: str,
        *,
        skip_colleges: set[str] | None = None,
        is_more_request: bool = False,
    ) -> str | None:
        match = self.get_reference_catalog().match_industry(user_query)
        if not match or not match.college_specialties:
            return None

        skip_colleges = skip_colleges or set()
        lines: list[str] = []
        seen_colleges: set[str] = set()
        added = 0

        entries = list(match.college_specialties)
        if match.key == "medicine":
            entries.sort(key=self.medicine_college_entry_priority)

        for entry in entries:
            college_name = str(entry.get("college", "")).strip()
            specialty_name = str(entry.get("specialty", "")).strip()
            professions = [str(item).strip() for item in entry.get("professions", []) if str(item).strip()]
            college_key = self.college_key(college_name)
            if not college_name or not specialty_name or college_key in seen_colleges or college_key in skip_colleges:
                continue

            if added == 0:
                if is_more_request:
                    lines.append(f"Нашёл ещё варианты по отрасли «{match.title}»:")
                else:
                    lines.append(f"По отрасли «{match.title}» в базе есть такие варианты:")

            lines.append(f"{added + 1}. {college_name} — {specialty_name}")
            if professions:
                lines.append(f"   После обучения: {', '.join(professions[:3])}")
            specialty_url = str(entry.get("specialty_url", "") or "").strip()
            if specialty_url:
                lines.append(f"   Подробнее о специальности: {specialty_url}")
            website = str(entry.get("website", "")).strip()
            if website:
                lines.append(f"   Сайт: {website}")

            seen_colleges.add(college_key)
            added += 1
            if added >= 3:
                break

        if added == 0:
            return None

        lines.append("")
        lines.append("Можно выбрать одну профессию из списка, и я покажу колледжи точнее.")
        return "\n".join(lines)

    def medicine_college_entry_priority(self, entry: dict[str, object]) -> tuple[int, int, str]:
        college = self.normalize_text(str(entry.get("college", ""))).replace("ё", "е")
        specialty = self.normalize_text(str(entry.get("specialty", ""))).replace("ё", "е")
        is_med_college = 0 if "медицинский колледж" in college or "училище сестер" in college else 1
        is_med_specialty = 0 if any(x in specialty for x in ["сестрин", "стомат", "медицин", "фармац", "лабораторная диагностика"]) else 1
        return (is_med_college, is_med_specialty, college)

    def medicine_profession_priority(self, profession: str) -> tuple[int, str]:
        normalized = self.normalize_text(profession).replace("ё", "е")
        is_core = 0 if any(x in normalized for x in ["медицин", "фельдшер", "фармацевт", "зубной", "оптометрист", "оптик"]) else 1
        return (is_core, normalized)

    def get_colleges_count(self, db: Session) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.doc_type == "college")
        result = db.scalar(stmt)
        return int(result or 0)

    def extract_college_name(self, doc: Document) -> str:
        return str(doc.metadata_json.get("college_name", "")).strip()

    def extract_specialty_name(self, doc: Document) -> str:
        return str(doc.metadata_json.get("specialty_name", "")).strip()

    def extract_specialty_url(self, doc: Document) -> str:
        return str(doc.metadata_json.get("specialty_url", "") or "").strip()

    def canonical_college_from_text(self, text: str) -> str | None:
        normalized = self.normalize_text(text).replace("ё", "е")
        compact = self.compact_key(text)
        # МПК — строго педагогический, ММПК — только музыкальный.
        if re.search(r"(^|\s)мпк($|\s)", normalized):
            return "Московский педагогический колледж"
        if "ммпк" in normalized or "музыкально педагогический" in normalized or "музыкально-педагогический" in normalized:
            return "Московский музыкально-педагогический колледж"
        for alias, canonical in KNOWN_COLLEGE_ALIASES.items():
            if alias in {"мпк", "ммпк"}:
                continue
            alias_norm = self.normalize_text(alias).replace("ё", "е")
            alias_compact = self.compact_key(alias)
            if alias_norm in normalized or (len(alias_compact) >= 3 and alias_compact in compact):
                return canonical
        return None

    def verification_hint(self, website: str | None = None) -> str:
        if website:
            return (
                "Я могу ошибаться в этой теме, поэтому лучше сверить информацию "
                f"в Атласе профессий: {ATLAS_URL} и на сайте колледжа: {website}."
            )
        return (
            "Я могу ошибаться в этой теме, поэтому лучше сверить информацию "
            f"в Атласе профессий: {ATLAS_URL} или на сайте конкретного колледжа."
        )

    def canonical_college_from_db(self, db: Session, text: str) -> str | None:
        normalized = self.normalize_text(text).replace("ё", "е")
        compact = self.compact_key(text)
        if not normalized:
            return None

        docs = db.scalars(select(Document).where(Document.doc_type == "college")).all()
        for doc in docs:
            college_name = self.extract_college_name(doc)
            aliases = doc.metadata_json.get("aliases", []) or []
            variants = [college_name, *[str(alias) for alias in aliases]]
            for variant in variants:
                value = self.normalize_text(variant).replace("ё", "е")
                if not value:
                    continue
                if value in normalized:
                    return college_name
                if len(value) <= 6 and re.search(rf"(^|\s){re.escape(value)}($|\s)", normalized):
                    return college_name
                value_compact = self.compact_key(variant)
                if len(value_compact) >= 3 and value_compact in compact:
                    return college_name
        return None

    def find_last_college_in_history(self, db: Session, messages) -> str | None:
        for msg in reversed(messages):
            text = str(getattr(msg, "content", "") or "")
            if not text:
                continue
            college = self.canonical_college_from_db(db, text) or self.canonical_college_from_text(text)
            if college:
                return college
        return None

    def looks_like_specific_unknown_institution_query(self, user_query: str) -> bool:
        q = self.normalize_text(user_query).replace("ё", "е")
        if self.is_faq_query(q):
            return False

        recommendation_markers = {
            "какие колледжи",
            "колледжи есть",
            "посоветуй",
            "куда поступ",
            "где учиться",
            "подбери",
        }
        if any(marker in q for marker in recommendation_markers):
            return False

        detail_markers = {
            "расскажи",
            "что за",
            "подробнее",
            "инфа",
            "адрес",
            "контакты",
            "сайт",
            "какие специальности",
        }
        institution_markers = {
            "колледж",
            "техникум",
            "университет",
            "академия",
            "институт",
            "вуз",
            "мгу",
            "мгту",
            "мирэа",
        }
        if "колледжи" in q and "какие специальности" not in q:
            return False
        return any(marker in q for marker in detail_markers) and any(marker in q for marker in institution_markers)

    def render_unknown_institution_response(self) -> str:
        return (
            "Я могу ошибаться в этой теме, поэтому не буду придумывать информацию по учебному заведению. "
            f"Лучше сверить его в Атласе профессий: {ATLAS_URL} или на официальном сайте колледжа.\n\n"
            "Если пришлёшь точное название из Атласа или с сайта колледжа, я попробую сопоставить его с моей локальной базой и отвечу аккуратнее."
        )

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
                f"По колледжу «{display_name}» я могу ошибаться с перечнем специальностей. "
                f"{self.verification_hint()}"
            )

        lines = [f"{display_name}: в моей базе вижу такие специальности:"]
        for idx, doc in enumerate(specialty_docs, start=1):
            spec = self.extract_specialty_name(doc)
            professions = doc.metadata_json.get("professions", []) or []
            line = f"{idx}. {spec}"
            if professions:
                line += f" — после обучения: {', '.join(str(p) for p in professions[:3])}"
            specialty_url = self.extract_specialty_url(doc)
            if specialty_url:
                line += f" — подробнее: {specialty_url}"
            lines.append(line)

        if college_card:
            contacts = college_card.metadata_json.get("contacts", []) or []
            website = college_card.metadata_json.get("website", "") or college_card.metadata_json.get("site", "")
            if website:
                lines.append(f"Сайт: {website}")
            if contacts:
                lines.append(f"Контакты: {'; '.join(str(c) for c in contacts[:4])}")

        website = ""
        if college_card:
            website = college_card.metadata_json.get("website", "") or college_card.metadata_json.get("site", "")
        lines.append(self.verification_hint(website or None))
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
        context_markers = {"специальн", "пункт", "вариант", "номер", "№", "давай", "возьмем", "возьмём", "расскажи", "подробнее"}
        has_context = any(marker in q for marker in context_markers)
        if not has_context and len(q.split()) > 2:
            return None
        for marker, num in mapping.items():
            if marker.isdigit():
                if q == marker or (has_context and re.search(rf"(^|\s){re.escape(marker)}($|\s)", q)):
                    return num
                continue
            if marker in q:
                return num
        return None

    def parse_last_numbered_specialty_choices(self, messages) -> list[tuple[str | None, str]]:
        """Ищет последний тематический нумерованный список из истории."""
        for msg in reversed(messages):
            if getattr(msg, "role", "") != "assistant":
                continue
            text = str(getattr(msg, "content", ""))
            text_norm = self.normalize_text(text)
            if not any(marker in text_norm for marker in ["специальн", "колледж", "професс", "направлен", "учиться", "обучения", "it"]):
                continue
            college_context = self.canonical_college_from_text(text)
            choices: list[tuple[str | None, str]] = []
            for line in text.splitlines():
                raw = line.strip()
                m = re.match(r"^(\d+)\.\s+(.*)$", raw)
                if not m:
                    continue
                item = re.sub(r"\*", "", m.group(2)).strip()
                parts = re.split(r"\s+—\s+|\s+-\s+|:", item, maxsplit=1)
                if len(parts) == 2 and self.looks_like_college_label(parts[0]):
                    college_for_item = parts[0].strip()
                    item = parts[1].strip()
                else:
                    college_for_item = college_context
                    item = parts[0].strip()
                # Отсекаем строки типа "Колледж:" / "Адреса:" / обычные рекомендации.
                bad_prefixes = ("колледж", "адрес", "контакт", "сайт", "почему", "следующий шаг")
                if item and not item.lower().startswith(bad_prefixes):
                    choices.append((college_for_item, item))
            if len(choices) >= 2:
                return choices
        return []

    def parse_last_numbered_specialties(self, messages) -> tuple[str | None, list[str]]:
        """Совместимая обёртка: возвращает общий колледж и список специальностей."""
        choices = self.parse_last_numbered_specialty_choices(messages)
        if not choices:
            return None, []
        colleges = [college for college, _ in choices if college]
        common_college = colleges[0] if colleges and len(set(colleges)) == 1 else None
        return common_college, [specialty for _, specialty in choices]

    def looks_like_college_label(self, text: str) -> bool:
        normalized = self.normalize_text(text)
        return any(marker in normalized for marker in ["колледж", "техникум", "комплекс", "центр", "мгпу", "ит.москва", "ит москва", "школа"])

    def college_key(self, name: str) -> str:
        return self.normalize_text(name).replace("ё", "е")

    def last_recommendation_context(self, messages) -> tuple[str, set[str]]:
        choices = self.parse_last_numbered_specialty_choices(messages)
        seen_colleges = {self.college_key(college) for college, _ in choices if college}
        specialties: list[str] = []
        seen_specialties: set[str] = set()

        for _, specialty in choices:
            key = self.normalize_text(specialty)
            if specialty and key not in seen_specialties:
                specialties.append(specialty)
                seen_specialties.add(key)

        query = " ".join(specialties[:3]).strip()
        if query:
            return f"{query}. Колледжи Москвы по этой специальности.", seen_colleges

        # Если в последнем ответе не было нумерованного списка, берём последний пользовательский запрос как тему.
        last_user = self.find_last_user_message(messages)
        return last_user, seen_colleges

    def render_specialty_detail_by_name(self, db: Session, specialty_name: str, college_name: str | None = None) -> str:
        # This path answers from DB specialty documents to avoid invented college lists.
        candidates = self.find_specialty_docs_by_query(db, specialty_name, college_name=college_name)
        if not candidates:
            return (
                f"Я понял, что речь про специальность «{specialty_name}», но могу ошибаться с деталями по ней. "
                f"{self.verification_hint()}"
            )
        doc = candidates[0]
        spec = self.extract_specialty_name(doc)
        professions = doc.metadata_json.get("professions", []) or []
        lines = [f"{spec} — что видно по моей базе:"]
        specialty_url = self.extract_specialty_url(doc)
        if specialty_url:
            lines.append(f"Страница в Атласе: {specialty_url}")
        if professions:
            lines.append(f"После обучения можно ориентироваться на профессии: {', '.join(str(p) for p in professions[:5])}.")

        if college_name:
            college = self.extract_college_name(doc)
            if college:
                lines.append(f"Колледж: {college}")
            content = re.sub(r"\s+", " ", (doc.content or "")).strip()
            if content:
                lines.append(content[:900])
        else:
            lines.append("В моей базе эта специальность есть в таких колледжах:")
            for idx, item in enumerate(candidates[:6], start=1):
                college = self.extract_college_name(item)
                website = str(item.metadata_json.get("website", "") or "").strip()
                line = f"{idx}. {college}"
                if website:
                    line += f" — {website}"
                lines.append(line)
            if len(candidates) > 6:
                lines.append(f"И ещё {len(candidates) - 6} вариантов в базе.")

        lines.append(self.verification_hint(doc.metadata_json.get("website", "") or None))
        return "\n".join(lines)

    def extract_specialty_topic(self, text: str) -> str:
        topic = self.normalize_text(text).replace("ё", "е")
        prefixes = [
            "расскажи подробнее про",
            "расскажи подробнее о",
            "расскажи подробнее об",
            "расскажи мне об",
            "расскажи про",
            "расскажи о",
            "расскажи об",
            "подробнее про",
            "инфа про",
            "что такое",
            "что за специальность",
            "что за",
        ]
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        topic = re.sub(r"\bспециальность\b", " ", topic)
        topic = re.sub(r"\s+", " ", topic)
        return topic.strip()

    def find_specialty_docs_by_query(
        self,
        db: Session,
        text: str,
        *,
        college_name: str | None = None,
    ) -> list[Document]:
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()
        target = self.extract_specialty_topic(text)
        if not target:
            return []

        # Token overlap handles user phrasing after removing prefixes like "tell me about".
        target_tokens = {token for token in target.split() if len(token) >= 3}
        scored: list[tuple[float, Document]] = []
        for doc in docs:
            spec_raw = self.extract_specialty_name(doc)
            spec = self.normalize_text(spec_raw).replace("ё", "е")
            if not spec:
                continue
            if college_name is not None and not self.college_name_matches(self.extract_college_name(doc), college_name):
                continue

            score = 0.0
            if target == spec:
                score += 10.0
            elif target in spec or spec in target:
                score += 8.0

            spec_tokens = {token for token in spec.split() if len(token) >= 3}
            overlap = target_tokens.intersection(spec_tokens)
            if overlap:
                score += len(overlap) / max(len(spec_tokens), 1) * 4.0

            if score >= 3.0:
                scored.append((score, doc))

        scored.sort(key=lambda item: (-item[0], self.extract_college_name(item[1]).lower()))

        seen: set[tuple[str, str]] = set()
        result: list[Document] = []
        for _, doc in scored:
            key = (self.college_key(self.extract_college_name(doc)), self.normalize_text(self.extract_specialty_name(doc)))
            if key in seen:
                continue
            seen.add(key)
            result.append(doc)
        return result

    def render_specialty_detail_by_query(self, db: Session, user_query: str) -> str | None:
        if not self.find_specialty_docs_by_query(db, user_query):
            return None
        return self.render_specialty_detail_by_name(db, self.extract_specialty_topic(user_query))

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

    def render_recommendation_fallback(
        self,
        documents: list[Document],
        user_query: str,
        *,
        skip_colleges: set[str] | None = None,
        is_more_request: bool = False,
    ) -> str:
        specialty_docs = [doc for doc in documents if doc.doc_type == "specialty"]
        skip_colleges = skip_colleges or set()
        if not specialty_docs:
            return (
                "Я могу ошибаться с подбором под такой запрос. "
                f"{self.verification_hint()} "
                "Могу предложить ближайшие варианты, если ты чуть уточнишь интерес: например, больше тянет к разработке, аналитике, безопасности или системам."
            )

        lines = []
        seen_colleges: set[str] = set()
        added = 0

        for doc in specialty_docs:
            college_name = self.extract_college_name(doc)
            specialty_name = self.extract_specialty_name(doc)
            professions = doc.metadata_json.get("professions", [])

            college_key = self.college_key(college_name)
            if not college_name or not specialty_name or college_name in seen_colleges or college_key in skip_colleges:
                continue

            if added == 0:
                if is_more_request:
                    lines.append("Нашёл ещё варианты по той же теме из доступных фактов:")
                else:
                    lines.append("Покажу ближайшие варианты из доступных фактов.")

            lines.append(f"{added + 1}. {college_name} — {specialty_name}")
            if professions:
                lines.append(f"   После обучения: {', '.join(professions[:3])}")
            specialty_url = self.extract_specialty_url(doc)
            if specialty_url:
                lines.append(f"   Подробнее о специальности: {specialty_url}")
            lines.append("   Почему это может подойти: направление связано с запросом и есть в базе колледжей Москвы.")
            seen_colleges.add(college_name)
            added += 1

            if added >= 3:
                break

        if added == 0:
            if is_more_request:
                return (
                    "Пока не вижу ещё колледжей по той же теме среди найденных документов. "
                    f"{self.verification_hint()}"
                )
            return (
                "Я могу ошибаться с подбором. Уточни, пожалуйста, что тебе ближе: программирование, аналитика, математика, безопасность или что-то ещё. "
                f"{self.verification_hint()}"
            )

        lines.append("")
        if added >= 3:
            lines.append("Если хочешь, могу показать ещё колледжи по этой же теме или коротко сравнить эти варианты.")
        else:
            lines.append("Если нужно, могу сравнить эти варианты простыми словами.")
        return "\n".join(lines)

    def render_detail_fallback(self, documents: list[Document]) -> str:
        college_docs = [doc for doc in documents if self.extract_college_name(doc)]
        if not college_docs:
            return (
                "Я могу ошибаться по этому колледжу и не хочу придумывать детали. "
                f"{self.verification_hint()}"
            )

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
                    specialty_url = self.extract_specialty_url(doc)
                    if specialty_url:
                        line += f" → {specialty_url}"
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
        website = college_card.metadata_json.get("website", "") if college_card else ""
        lines.append(self.verification_hint(website or None))
        return "\n".join(lines)

    def render_faq_fallback(self, documents: list[Document]) -> str:
        faq_docs = [doc for doc in documents if doc.doc_type == "faq"][:3]
        if not faq_docs:
            return random.choice([
                f"Я могу ошибаться с этим правилом, поэтому лучше сверить его на mos.ru, в Атласе профессий ({ATLAS_URL}) или у выбранного колледжа.",
                f"Я могу ошибаться: точного правила под такой вопрос у меня сейчас нет. Надёжнее проверить mos.ru, Атлас профессий ({ATLAS_URL}) или сайт колледжа.",
                f"Я могу ошибаться, поэтому не хочу придумывать официальный порядок. Лучше сверить вопрос на mos.ru, в Атласе профессий ({ATLAS_URL}) или у приёмной комиссии.",
                f"Я могу ошибаться по этой формулировке и не уверен в фактах. Проверь, пожалуйста, mos.ru, Атлас профессий ({ATLAS_URL}) или сайт конкретного колледжа.",
                f"Я могу ошибаться в такой детали. Безопаснее посмотреть официальные правила на mos.ru или в Атласе профессий: {ATLAS_URL}.",
                f"Я могу ошибаться, потому что здесь нужен официальный источник. Я бы сверил mos.ru, Атлас профессий ({ATLAS_URL}) и сайт колледжа.",
                f"Я могу ошибаться: у меня нет достаточно точного FAQ-факта для уверенного ответа. Лучше проверить Атлас профессий ({ATLAS_URL}) или обратиться в приёмную комиссию.",
                f"Я могу ошибаться, а ложная информация тут вредна. Лучше уточнить этот пункт на mos.ru, в Атласе профессий ({ATLAS_URL}) или у колледжа.",
                f"Я могу ошибаться по этому вопросу. Могу подсказать общую логику, но проверку делай через mos.ru или Атлас: {ATLAS_URL}.",
                f"Я могу ошибаться: похоже на вопрос к правилам приёма, где важны детали. Сверь mos.ru, Атлас профессий ({ATLAS_URL}) или сайт выбранного колледжа.",
                f"Я могу ошибаться, поэтому не буду угадывать норму приёма. Самый надёжный путь — mos.ru, Атлас профессий ({ATLAS_URL}) или приёмная комиссия колледжа.",
                f"Я могу ошибаться по этой части, поэтому лучше проверить первоисточник: mos.ru, Атлас профессий ({ATLAS_URL}) или сайт колледжа.",
            ])

        answer = faq_docs[0].content.strip()
        answer += "\n\nЕсли хочешь, могу объяснить это проще."
        return answer

    def should_simplify_previous_answer(self, user_query: str, previous_messages) -> bool:
        if not (self.is_followup_for_simplify(user_query) or self.is_general_explain_followup(user_query)):
            return False

        last_assistant = self.find_last_assistant_message(previous_messages)
        if not last_assistant:
            return False

        text = self.normalize_text(last_assistant).replace("ё", "е")
        return (
            "могу объяснить это проще" in text
            or "объяснить проще" in text
            or "простыми словами" in text
        )

    def render_simple_explanation(self, recent_messages) -> str:
        messages = list(recent_messages)
        if messages and getattr(messages[-1], "role", "") == "user":
            messages = messages[:-1]
        last_assistant = self.find_last_assistant_message(messages)
        if not last_assistant:
            return "Хорошо. Напиши, что именно объяснить проще, и я переформулирую без сложных формулировок."

        if "Если хочешь, могу объяснить это проще." in last_assistant:
            source = last_assistant.replace("Если хочешь, могу объяснить это проще.", "").strip()
            source = re.sub(r"\s+", " ", source)

            source_norm = self.normalize_text(source).replace("ё", "е")
            if "отсроч" in source_norm and "арм" in source_norm:
                return (
                    "Проще говоря: отсрочка от армии возможна, если ты учишься в колледже очно и получаешь среднее профессиональное образование впервые.\n\n"
                    "Если это уже второе СПО, по ответу из базы отсрочка не действует. Для своей ситуации лучше сверить детали с колледжем или военкоматом."
                )

            if "документ" in source_norm and "mos.ru" in source_norm:
                return (
                    "Проще говоря:\n"
                    "1. Если ты московский выпускник 2025 или 2026 года, данные на mos.ru могут заполниться автоматически, если они уже есть в личном кабинете.\n"
                    "2. Остальным обычно нужны личные данные, контакты, СНИЛС, данные документа личности, регистрация и сведения об образовании.\n"
                    "3. Скан-копии нужны для документа личности и документа об образовании.\n"
                    "4. Если есть льготы, ОВЗ или индивидуальные достижения, подтверждения прикладывают отдельно.\n\n"
                    "Перед подачей лучше проверить форму заявления на mos.ru и требования выбранного колледжа."
                )

            return (
                "Проще говоря: " + source[:900].strip()
                + "\n\nЕсли хочешь, могу дальше разложить это по шагам: что делать сначала, что подготовить и где проверить."
            )

        system_prompt = (
            "Ты помощник по колледжам Москвы. Отвечай только на русском языке. "
            "Перепиши объяснение проще и короче, обычным человеческим языком. "
            "Не добавляй новых фактов. Не выдумывай. "
            "Если в тексте есть официальный смысл, сохрани его, но объясни понятнее."
        )
        user_prompt = f"Объясни проще вот этот ответ:\n\n{last_assistant}"
        try:
            result = self.clean_llm_output(self.call_llm(system_prompt, user_prompt))
            if result and not self.contains_cjk(result):
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
            "Если уверенности не хватает, мягко скажи, что можешь ошибаться, и предложи сверить информацию в Атласе профессий или на сайте колледжа. "
            "Не формулируй отказ через отсутствие данных в локальной базе. "
            "Дай 1-3 ближайших варианта. "
            "По каждому варианту укажи: колледж, специальность, 1-3 профессии после обучения и коротко объясни, почему вариант подходит. "
            "Не дублируй один и тот же колледж больше одного раза. "
            "Ответ должен быть компактным: не больше 1700 символов. "
            "В конце предложи один следующий шаг: объяснить профессию, сравнить варианты или сузить выбор."
        )
        user_prompt = (
            f"Запрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=6)}\n\n"
            f"Атлас профессий для проверки: {ATLAS_URL}\n\n"
            "Сделай ответ полезным, естественным и не перегруженным."
        )
        return system_prompt, user_prompt

    def build_detail_prompt(self, user_query: str, documents: list[Document]) -> tuple[str, str]:
        system_prompt = (
            "Ты дружелюбный помощник по колледжам Москвы. "
            "Отвечай только на русском языке. Запрещены китайские, японские, корейские и случайные английские вставки. Не используй markdown-заголовки вида ###. "
            "Нельзя выдумывать факты: не пиши про престиж, отзывы, практику, работодателей, качество, круглогодичное обучение или связи с компаниями, если этого нет в фактах. "
            "Расскажи про конкретный колледж по фактам из контекста. "
            "Если фактов не хватает, мягко скажи, что можешь ошибаться, и предложи сверить Атлас профессий или сайт колледжа. "
            "Не формулируй отказ через отсутствие данных в локальной базе. "
            "Структура: коротко что это за колледж; 3-5 заметных специальностей; кем можно работать после; адреса/контакты/сайт, если есть. "
            "Ответ должен быть полезным, но компактным: не больше 2200 символов."
        )
        user_prompt = (
            f"Запрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=8)}\n\n"
            f"Атлас профессий для проверки: {ATLAS_URL}\n\n"
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
            "Если точного факта нет, мягко скажи, что можешь ошибаться по этой части, и предложи сверить mos.ru, Атлас профессий или сайт колледжа. "
            "Не формулируй отказ через отсутствие данных в локальной базе. "
            "В конце добавь: 'Если хочешь, могу объяснить это проще.' "
            "Ответ не длиннее 1700 символов."
        )
        user_prompt = (
            f"Вопрос пользователя:\n{user_query}\n\n"
            f"Факты из базы:\n{self.compact_docs(documents, limit=6)}\n\n"
            f"Атлас профессий для проверки: {ATLAS_URL}"
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
            "Если точных данных нет, мягко скажи, что можешь ошибаться, и предложи сверить Атлас профессий или сайт колледжа. "
            "Не формулируй отказ через отсутствие данных в локальной базе. "
            "Ответ должен быть коротким и полезным: до 1200 символов."
        )
        user_prompt = (
            f"Предыдущая тема пользователя:\n{last_user}\n\n"
            f"Предыдущий ответ ассистента:\n{last_assistant}\n\n"
            f"Текущий уточняющий вопрос:\n{user_query}\n\n"
            f"Факты из базы по теме:\n{self.compact_docs(documents, limit=5)}\n\n"
            f"Атлас профессий для проверки: {ATLAS_URL}"
        )
        return system_prompt, user_prompt

    def try_llm_answer(self, mode: str, user_query: str, documents: list[Document], recent_messages) -> str:
        # Фактические режимы рендерим сами: так модель не сможет добавить колледж, которого нет в RAG.
        if mode == "recommend":
            return self.render_recommendation_fallback(documents, user_query)
        if mode == "detail":
            return self.render_detail_fallback(documents)
        if mode == "faq":
            return self.render_faq_fallback(documents)
        if mode == "context":
            return self.render_context_fallback(user_query, documents, recent_messages)

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
                    specialty_url = self.extract_specialty_url(doc)
                    if specialty_url:
                        line += f" → {specialty_url}"
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
                f"Я беру ответ из локальной базы колледжей и FAQ проекта. Если могу ошибаться, предлагаю сверить Атлас профессий: {ATLAS_URL}, сайт колледжа или приёмную комиссию.",
                f"Основа ответа — документы из базы проекта: колледжи, специальности, профессии после обучения, адреса и часть FAQ. Важные детали лучше проверять в Атласе профессий: {ATLAS_URL} или на сайте колледжа.",
            ],
            "safety": [
                "Я не помогаю с незаконными или опасными действиями. Если тебе интересна эта область как профессия, могу безопасно рассказать про информационную безопасность и колледжи, где есть близкие специальности.",
                "С инструкциями для вреда, взлома или обхода правил я не помогаю. Зато могу объяснить, чем занимается специалист по безопасности и какие учебные направления стоит посмотреть.",
                "Такой запрос я не буду разбирать пошагово. Если цель учебная и легальная, переформулируй: например, «куда поступать на информационную безопасность» или «что делает специалист по ИБ».",
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
            return random.choice([
                "Я не кулинарный бот и не буду придумывать рецепт. Но если тебе интересна готовка как профессия, могу подсказать колледжи с направлением ‘Поварское и кондитерское дело’.",
                "Рецепты — не моя зона. Зато могу помочь посмотреть, где учиться на повара или кондитера в московских колледжах.",
                "Готовку как домашний рецепт я не разбираю, но могу связать интерес к кухне с профессией и подобрать близкие специальности.",
            ])
        if "теорем" in q or "алгоритм" in q or "код" in q or "задач" in q:
            return random.choice([
                "Я здесь именно как помощник по колледжам Москвы и поступлению. Учебные задачи, теоремы и код лучше разбирать отдельно.\n\nЕсли хочешь связать это с выбором профессии, могу подсказать, где учиться на программиста, инженера или аналитика.",
                "Код и домашние задачи я не решаю. Но если вопрос про выбор направления, могу помочь понять, подойдут ли тебе программирование, аналитика, инженерия или ИБ.",
                "Это выходит за мой рабочий сценарий. Могу перевести тему в профориентацию: какие колледжи и специальности смотреть, если тебе интересны алгоритмы, IT или инженерия.",
            ])
        return random.choice([
            "Это не совсем моя тема. Я лучше всего помогаю с колледжами Москвы, специальностями и поступлением.\n\nМожешь спросить: ‘куда поступать на логиста’, ‘расскажи про МПК’ или ‘какие документы нужны’.",
            "С этим я не лучший помощник. Давай вернёмся к колледжам, профессиям или поступлению: так я отвечу точнее и полезнее.",
            "Я держусь темы московских колледжей и профориентации. Если хочешь, переформулируй вопрос через профессию или специальность.",
        ])

    def compact_history_text(self, messages, limit: int = 8) -> str:
        chunks: list[str] = []
        for msg in messages[-limit:]:
            role = getattr(msg, "role", "")
            content = re.sub(r"\s+", " ", str(getattr(msg, "content", "")).strip())
            if content:
                chunks.append(f"{role}: {content[:500]}")
        return "\n".join(chunks) or "Истории нет."

    def render_chat_answer(self, decision: RouterDecision, recent_messages) -> str:
        # В chat-режиме не называем колледжи: без RAG-контекста это самый частый источник галлюцинаций.
        q = self.normalize_text(decision.normalized_query)
        if self.is_short_followup(q):
            return random.choice([
                "Понял. Напиши чуть конкретнее, что продолжить: показать ещё колледжи, сравнить варианты или объяснить профессию?",
                "Давай продолжим, только чуть конкретнее: нужны другие колледжи, контакты, специальности или правила поступления?",
                "Согласен. Напиши чуть конкретнее, в какую сторону идём: ещё варианты, сравнение или подробнее про прошлый колледж?",
                "Окей. Чтобы не гадать, напиши чуть конкретнее: колледжи, профессии после обучения, адреса/контакты или поступление.",
                "Хорошо. Могу продолжить по прошлой теме, но напиши чуть конкретнее: «ещё колледжи», «сравни» или «подробнее».",
            ])
        return random.choice([
            "Я лучше отвечаю, когда вопрос привязан к колледжу, профессии, отрасли или поступлению. Попробуй написать: «где учат на ...» или «сравни ... и ...».",
            "Похоже, вопрос получился слишком общий. Могу помочь по трём темам: подобрать колледж, объяснить специальность или ответить про поступление.",
            "Я не хочу угадывать. Напиши чуть конкретнее: название колледжа, профессию, отрасль или вопрос по mos.ru.",
            "Давай сформулируем точнее: тебе нужны колледжи по профессии, контакты колледжа, сравнение вариантов или правила приёма?",
            "Сейчас не хватает опоры для ответа. Можно спросить так: «где учат на сварщика», «какие колледжи в медицине», «дай адрес КП 11».",
            "Я могу промахнуться, если отвечу на такую формулировку. Уточни предмет: колледж, специальность, профессия, отрасль или поступление.",
            "Пока не понимаю, какой сценарий нужен. Выбери направление: профориентация, рекомендация колледжа, контакты или FAQ по поступлению.",
            "Давай без гадания: напиши профессию или колледж, а я проверю по базе и отвечу аккуратно.",
            "Мне нужно чуть больше контекста. Например: «колледжи для дизайнеров», «сроки подачи заявления», «контакты КАИТ 20».",
            "Вижу сообщение, но не вижу понятной темы. Могу подобрать колледжи, сравнить варианты или объяснить правила поступления.",
            "Чтобы ответ был полезным, уточни одно слово: профессия, колледж, отрасль или поступление.",
            "Я не буду придумывать. Переформулируй через цель: кем хочешь стать, какой колледж смотришь или какой вопрос по приёму интересует.",
            "Пока это не похоже на вопрос из моей зоны. Если свяжешь его с колледжем, профессией или поступлением, я помогу.",
            "Могу помочь, но нужно сузить тему. Напиши, например: «медицина», «IT», «КП 11», «документы» или «дни открытых дверей».",
            "Дай мне одну зацепку: название колледжа, профессию или отрасль. Тогда отвечу по базе, без выдумок.",
        ])

    def render_smart_clarification(self, user_query: str, previous_messages) -> str:
        q = self.normalize_text(user_query).replace("ё", "е")
        if "нейросет" in q or "искусственн интеллект" in q:
            return (
                "Похоже, тебе интересны нейросети и ИИ. В базе это лучше искать не словом «нейросети», а через IT-направления: "
                "программирование, интеллектуальные интегрированные системы, базы данных и разработку ПО.\n\n"
                "Могу следующим сообщением показать колледжи по ближайшему IT-направлению."
            )
        if "форма" in q or "носить форму" in q:
            return (
                "Правила формы одежды зависят от конкретного колледжа, а в моей базе этого нет. "
                "Лучше проверить сайт колледжа или спросить приёмную комиссию."
            )
        if "подготов" in q and "сесс" in q:
            return (
                "Это скорее вопрос про учёбу, а не про поступление. Общий совет: уточнить список зачётов/экзаменов у преподавателей, "
                "разбить темы по дням и сначала закрыть долги по практическим работам.\n\n"
                "Если хочешь, могу помочь связать это с выбором специальности: где будет больше практики, техники, общения или теории."
            )

        last_topic = self.find_last_meaningful_user_message(previous_messages)
        options = [
            "подобрать колледжи по профессии",
            "сравнить 2–3 колледжа",
            "дать контакты или адрес колледжа",
            "ответить про поступление на mos.ru",
            "помочь выбрать направление",
        ]
        if last_topic:
            return (
                f"Я могу понять это как продолжение темы «{last_topic}», но формулировка неоднозначная.\n\n"
                "Могу сделать одно из этого:\n"
                f"1. {options[0]}.\n"
                f"2. {options[1]}.\n"
                f"3. {options[2]}.\n\n"
                "Напиши номер или коротко уточни тему."
            )
        return (
            "Я попробовал распознать вопрос, но вижу несколько возможных тем.\n\n"
            "Могу помочь так:\n"
            f"1. {options[0]}.\n"
            f"2. {options[1]}.\n"
            f"3. {options[3]}.\n"
            f"4. {options[4]}.\n\n"
            "Напиши номер или добавь название колледжа/профессии."
        )

    def render_career_guidance_answer(self, decision: RouterDecision, recent_messages) -> str:
        q = self.normalize_text(decision.normalized_query).replace("ё", "е")
        history = self.compact_history_text(recent_messages, limit=8).lower()
        full = f"{history}\n{q}"

        if any(x in q for x in ["не знаю кем", "не знаю что хочу", "не знаю куда", "помоги выбрать", "профориентация"]):
            return (
                "Нормально не знать, кем хочешь быть. Давай начнём с простого выбора, без случайных колледжей.\n\n"
                "Что тебе ближе сейчас?\n"
                "1. Люди и помощь — медицина, педагогика, социальная работа.\n"
                "2. Техника и компьютеры — IT, сети, электроника, инженерия.\n"
                "3. Творчество — дизайн, фото, медиа, музыка.\n"
                "4. Организация и документы — право, финансы, логистика, сервис.\n\n"
                "Ответь 1–2 словами, что больше цепляет, и я предложу направления."
            )

        if any(x in q for x in ["не хочу код", "не хочу программ", "не нравится код", "не хочу только сидеть", "не только сидеть в коде", "без кода"]):
            return (
                "Тогда не надо упираться именно в разработку. В IT есть направления, где кода меньше, а техники и практических задач больше.\n\n"
                "Я бы смотрел так:\n"
                "1. Сетевое и системное администрирование — компьютеры, сети, серверы, настройка и поддержка инфраструктуры.\n"
                "2. Компьютерные системы и комплексы — больше про устройство техники, оборудование и сопровождение систем.\n"
                "3. Информационная безопасность — если интересна защита систем, но важно держаться легальной и defensive-стороны.\n\n"
                "Следующий шаг: могу подобрать колледжи по этим IT-направлениям или сравнить их простыми словами."
            )

        if any(x in q for x in ["желез", "техника", "сервер", "сети", "компьютер"]) and any(
            x in history for x in ["айти", "it", "код", "программ", "информ"]
        ):
            return (
                "Если тебе ближе техника и железо, я бы смещал фокус с разработки на инфраструктуру.\n\n"
                "Подходящие направления:\n"
                "1. Сетевое и системное администрирование — сети, серверы, настройка рабочих мест и сервисов.\n"
                "2. Компьютерные системы и комплексы — устройство компьютеров, оборудование, диагностика и сопровождение.\n"
                "3. Инфокоммуникационные сети и системы связи — если интересны связь, оборудование и передача данных.\n\n"
                "Дальше можно подобрать колледжи именно под эти специальности, не смешивая их с чистой веб-разработкой."
            )

        if (self.is_followup_for_detail(q) or self.is_general_explain_followup(q)) and recent_messages:
            last_assistant = self.find_last_assistant_message(recent_messages)
            if last_assistant:
                system_prompt = (
                    "Ты профориентационный помощник по колледжам Москвы. "
                    "Пользователь просит подробнее раскрыть прошлую профориентационную тему. "
                    "Не спрашивай, о чём речь: используй прошлый ответ. "
                    "Не называй случайные колледжи и не выдумывай факты о них. "
                    "Объясни направления, чем там занимаются, кому подходит, и предложи один следующий шаг. "
                    "Если нужна проверка фактов, мягко предложи Атлас профессий или сайт колледжа. "
                    "Отвечай только на русском, до 1800 символов."
                )
                user_prompt = (
                    f"История:\n{self.compact_history_text(recent_messages)}\n\n"
                    f"Прошлый ответ:\n{last_assistant}\n\n"
                    f"Текущий запрос пользователя:\n{decision.normalized_query}\n\n"
                    f"Атлас профессий для проверки: {ATLAS_URL}"
                )
                try:
                    result = self.clean_llm_output(self.call_llm(system_prompt, user_prompt))
                    if result and len(result) >= 30 and not self.contains_cjk(result):
                        return result
                except Exception as e:
                    logger.warning(f"career guidance detail failed: {e}")

                return (
                    "Продолжу прошлую тему подробнее. Смотри не только на название направления, а на реальные задачи: "
                    "будешь ли ты больше работать с людьми, техникой, творчеством, документами или компьютерами.\n\n"
                    "Хороший следующий шаг — выбрать 2–3 близких направления и уже потом смотреть колледжи, специальности и профессии после обучения."
                )

        # Жёсткие профориентационные сценарии без LLM, чтобы не повторять старые шаблоны.
        if any(x in full for x in ["медицин", "здоров", "биолог", "сестрин"]) and any(x in full for x in ["помощ", "люд", "забот"]):
            return (
                "Тут хорошо сходятся два мотива: медицина и помощь людям. Я бы смотрел не один колледж сразу, а 3 близких направления:\n\n"
                "1. Сестринское дело — если хочется реальной практики, ухода за пациентами и работы в медицине.\n"
                "2. Лабораторная диагностика / фармация — если интересна медицина, но больше тянет к анализам, препаратам и точной работе.\n"
                "3. Медицинский массаж или социальная помощь — если важны восстановление, поддержка и работа с людьми.\n\n"
                "Следующий шаг: могу подобрать колледжи по медицине из базы или отдельно показать профессии в этой отрасли."
            )

        if any(x in full for x in ["дети", "детьм", "ребен", "ребён", "дошколь", "помощ", "овз", "пенсион", "люд", "общаться"]):
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
        more_colleges_request = self.is_more_colleges_request(user_query)
        more_colleges_seen: set[str] = set()
        if more_colleges_request:
            # Для "ещё колледжи" держим прошлую тему и не показываем те же варианты повторно.
            more_query, more_colleges_seen = self.last_recommendation_context(previous_messages)
            more_colleges_seen.update(self.collect_seen_colleges_from_history(db, previous_messages))
            if more_query:
                decision.mode = "recommend_colleges"
                decision.normalized_query = more_query
                decision.topic = "другие колледжи по прошлой теме"
                decision.needs_retrieval = True
                decision.use_history = True

        # Жёсткие сценарии до retrieval и до генерации большого ответа.
        if decision.mode == "script":
            answer = self.pick_script_answer(decision, user_query)
            return self.save_and_return(db, session, user_query, answer, "script")

        if decision.mode == "out_of_scope":
            answer = self.render_out_of_scope(user_query)
            return self.save_and_return(db, session, user_query, answer, "out_of_scope")

        if self.is_staff_query(user_query):
            answer = self.render_staff_unknown_answer(db, user_query)
            return self.save_and_return(db, session, user_query, answer, "faq")

        if self.is_compare_colleges_query(user_query):
            answer = self.render_college_comparison(db, user_query, previous_messages)
            return self.save_and_return(db, session, user_query, answer, "compare")

        common_faq_answer = self.render_common_faq_answer(user_query)
        if common_faq_answer:
            return self.save_and_return(db, session, user_query, common_faq_answer, "faq")

        if self.is_industry_colleges_query(user_query):
            answer = self.render_catalog_recommendation(user_query)
            if answer:
                return self.save_and_return(db, session, user_query, answer, "recommend_colleges")

        if self.is_industry_professions_query(user_query):
            answer = self.render_industry_professions_from_catalog(user_query)
            if answer:
                return self.save_and_return(db, session, user_query, answer, "recommend_colleges")

        if self.is_catalog_recommendation_query(user_query):
            answer = self.render_catalog_recommendation(user_query)
            if answer:
                return self.save_and_return(db, session, user_query, answer, "recommend_colleges")

        db_college = None
        should_match_college = (
            self.is_detail_query(user_query)
            or self.is_contact_query(user_query)
            or self.is_all_specialties_request(user_query)
            or self.looks_like_specific_unknown_institution_query(user_query)
        )
        if should_match_college:
            db_college = self.canonical_college_from_db(db, user_query)

        if db_college and decision.mode not in {"faq", "career_guidance"}:
            decision.college = db_college
            decision.topic = db_college
            decision.normalized_query = (
                f"{db_college}. Расскажи подробнее и покажи специальности."
                if self.is_all_specialties_request(user_query)
                else db_college
            )
            if decision.mode not in {"detail", "detail_more", "recommend_colleges"}:
                decision.mode = "detail_more" if self.is_all_specialties_request(user_query) else "detail"

        if (
            not db_college
            and not self.canonical_college_from_text(user_query)
            and self.looks_like_specific_unknown_institution_query(user_query)
        ):
            answer = self.render_unknown_institution_response()
            return self.save_and_return(db, session, user_query, answer, "clarify")

        if self.is_college_existence_question(user_query):
            history_college = self.find_last_college_in_history(db, previous_messages)
            checked_college = db_college or self.canonical_college_from_text(user_query) or history_college
            if checked_college:
                answer = (
                    f"Да, {checked_college} есть в моей базе московских колледжей. "
                    f"{self.verification_hint()}"
                )
            else:
                answer = (
                    "Я не могу подтвердить этот колледж по своей базе и не хочу придумывать. "
                    f"{self.verification_hint()}"
                )
            return self.save_and_return(db, session, user_query, answer, "clarify")

        if self.is_college_count_query(user_query):
            count = self.get_colleges_count(db)
            answer = f"По моей базе сейчас {count} колледжей Москвы."
            return self.save_and_return(db, session, user_query, answer, "faq")

        # Детерминированный ответ на "все специальности колледжа" — без Qwen и без retriever.
        requested_college = (
            db_college
            or self.canonical_college_from_text(user_query)
            or decision.college
            or (
                self.find_last_college_in_history(db, previous_messages)
                if self.is_all_specialties_request(user_query) or self.is_contact_query(user_query)
                else None
            )
        )
        if requested_college and self.is_all_specialties_request(user_query):
            answer = self.render_all_specialties_for_college(db, requested_college)
            return self.save_and_return(db, session, user_query, answer, "detail_more")

        if requested_college and self.is_contact_query(user_query):
            answer = self.render_college_contacts(db, requested_college, user_query)
            return self.save_and_return(db, session, user_query, answer, "detail")

        if not requested_college and self.is_detail_query(user_query):
            answer = self.render_specialty_detail_by_query(db, user_query)
            if answer:
                return self.save_and_return(db, session, user_query, answer, "detail")

        # Детерминированный ответ на "третью/вторую специальность" из прошлого списка.
        ordinal = self.extract_ordinal_request(user_query)
        if ordinal is not None:
            choices = self.parse_last_numbered_specialty_choices(previous_messages)
            if 1 <= ordinal <= len(choices):
                college_from_list, specialty_from_list = choices[ordinal - 1]
                answer = self.render_specialty_detail_by_name(db, specialty_from_list, college_from_list)
                return self.save_and_return(db, session, user_query, answer, "detail_more")

        if decision.mode != "career_guidance" and self.is_followup_for_detail(user_query):
            answer = self.render_detail_followup_from_history(db, previous_messages)
            if answer:
                return self.save_and_return(db, session, user_query, answer, "detail_more")

        # Исправление после ошибки: "при чём тут юриспруденция/веб-разработка".
        if any(mark in self.normalize_text(user_query) for mark in ["при чем тут", "при чём тут", "не то", "не об этом"]):
            last_college = self.canonical_college_from_text(self.find_last_assistant_message(previous_messages)) or self.canonical_college_from_text(self.find_last_user_message(previous_messages))
            if last_college:
                answer = self.render_all_specialties_for_college(db, last_college)
                return self.save_and_return(db, session, user_query, answer, "detail_more")
            answer = "Да, ты прав — я съехал не в ту тему. Напиши колледж или специальность ещё раз, и я отвечу строго по базе."
            return self.save_and_return(db, session, user_query, answer, "script")

        if self.should_simplify_previous_answer(user_query, previous_messages):
            answer = self.render_simple_explanation(previous_messages + [])
            return self.save_and_return(db, session, user_query, answer, "faq_simple")

        if decision.mode == "chat":
            answer = self.render_smart_clarification(user_query, previous_messages)
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
        if decision.mode == "recommend_colleges":
            search_top_k = max(top_k, 18 if more_colleges_request else 10)
        if decision.mode == "faq":
            search_top_k = max(top_k, 6)

        documents = self.retriever.search(
            db=db,
            query=retrieval_query,
            top_k=search_top_k,
            diversify_by_college=diversify,
        )
        top_doc_types = [doc.doc_type for doc in documents[:5]]
        top_titles = [doc.title for doc in documents[:3]]
        logger.info(
            "RAG result: mode=%s answer_mode=%s query=%r count=%s types=%s titles=%s",
            decision.mode,
            answer_mode,
            retrieval_query[:300],
            len(documents),
            top_doc_types,
            top_titles,
        )

        # Вопросы про ОВЗ/инвалидность лучше отвечать устойчивым официальным шаблоном.
        q_norm = self.normalize_text(user_query)
        has_ovz_context = any(x in q_norm for x in ["овз", "инвалид", "особые условия", "специальные условия", "не могу сдавать", "как все"])
        if decision.mode == "faq" and has_ovz_context:
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

        if decision.mode == "faq":
            answer = self.render_faq_fallback(documents)
            self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
            return {
                "session_id": session.session_id,
                "answer": answer,
                "dialog_mode": "faq",
            }

        if decision.mode == "recommend_colleges":
            catalog_query = decision.normalized_query if more_colleges_request else user_query
            answer = self.render_catalog_recommendation(
                catalog_query,
                skip_colleges=more_colleges_seen,
                is_more_request=more_colleges_request,
            )
            if answer:
                self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
                return {
                    "session_id": session.session_id,
                    "answer": answer,
                    "dialog_mode": "recommend_colleges",
                }

            answer = self.render_recommendation_fallback(
                documents,
                user_query,
                skip_colleges=more_colleges_seen,
                is_more_request=more_colleges_request,
            )
            self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
            return {
                "session_id": session.session_id,
                "answer": answer,
                "dialog_mode": "recommend_colleges",
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
