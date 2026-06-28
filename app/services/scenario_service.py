from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.repository import Document
from app.logger import get_logger
from app.services.chat_service import ATLAS_URL, ChatService
from app.services.session_service import SessionService

logger = get_logger(__name__)


PARENT_LABEL = "Родитель"
APPLICANT_LABEL = "Абитуриент / поступающий"

MAIN_MENU = [
    "Выбрать колледж",
    "Выбрать профессию",
    "Узнать о порядке поступления",
    "Свой вопрос",
]

USER_TYPE_BUTTONS = [PARENT_LABEL, APPLICANT_LABEL]
BACK_BUTTON = "Назад"
MAIN_MENU_BUTTON = "Главное меню"
END_SESSION_BUTTON = "Завершить сессию"
COLLEGE_START_BUTTONS = [
    "Найти конкретный колледж",
    "Помочь выбрать колледж",
    MAIN_MENU_BUTTON,
]
COLLEGE_FOUND_BUTTONS = [
    "Контакты и адреса",
    "Все специальности",
    "Порядок поступления",
    "Задать вопрос про этот колледж",
    "Новый поиск",
    MAIN_MENU_BUTTON,
]
COLLEGE_CHOOSE_BUTTONS = [
    "Да, специальность выбрана",
    "Нет, ещё выбираю",
    "Не знаю, с чего начать",
    BACK_BUTTON,
    MAIN_MENU_BUTTON,
]
PROFESSION_START_BUTTONS = [
    "Выбрать отрасль",
    "Я знаю профессию",
    "Я не знаю, что выбрать",
    MAIN_MENU_BUTTON,
]
ADMISSION_TOPICS: list[tuple[str, str, str]] = [
    ("application", "Как подать заявление", "как подать заявление на поступление в колледж Москвы через mos.ru"),
    ("documents", "Какие документы нужны", "какие документы нужны для поступления в колледж Москвы"),
    ("deadlines", "Сроки поступления", "сроки поступления в колледж Москвы в 2026 году"),
    ("exams", "Вступительные испытания", "вступительные испытания при поступлении в колледж Москвы"),
    ("ovz", "ОВЗ и специальные условия", "особые условия и ОВЗ при поступлении в колледж"),
    ("army", "Отсрочка от армии", "отсрочка от армии при обучении в колледже"),
    ("budget", "Бюджет и конкурс", "бюджетные места конкурс и зачисление в колледж Москвы"),
    ("rules_2026", "Правила приёма в 2026 году", "правила приёма в колледжи Москвы в 2026 году документы сроки заявление"),
    ("svo_priority", "СВО и первоочередное право", "первоочередное право зачисления СВО дети участников СВО льготы поступление"),
]
HIDDEN_ADMISSION_TOPIC_SLUGS = {"svo_priority"}
ADMISSION_TOPIC_BUTTONS = [label for slug, label, _ in ADMISSION_TOPICS if slug not in HIDDEN_ADMISSION_TOPIC_SLUGS] + [
    "Другой вопрос про поступление",
    MAIN_MENU_BUTTON,
]
ADMISSION_QUERIES = {slug: query for slug, _, query in ADMISSION_TOPICS}
ADMISSION_RELATED_TOPICS: dict[str, list[str]] = {
    "ovz": [
        "Какие документы нужны",
        "Как подать заявление",
        "Вступительные испытания",
        "Сроки поступления",
    ],
    "documents": [
        "Как подать заявление",
        "Сроки поступления",
        "Бюджет и конкурс",
        "ОВЗ и специальные условия",
    ],
    "svo_priority": [
        "Какие документы нужны",
        "Как подать заявление",
        "Бюджет и конкурс",
        "Сроки поступления",
    ],
    "army": [
        "Отсрочка от армии",
        "Поступление после колледжа",
        "Документы для поступления",
    ],
    "exams": [
        "Как подать заявление",
        "Какие документы нужны",
        "Контакты колледжа",
        "Выбрать колледж",
    ],
}

INDUSTRY_BUTTONS: list[tuple[str, str]] = [
    ("IT и цифровые технологии", "it"),
    ("Дизайн и творчество", "design"),
    ("Педагогика и работа с детьми", "education"),
    ("Медицина и социальная помощь", "medicine"),
    ("Право и безопасность", "law"),
    ("Финансы и экономика", "finance"),
    ("Туризм и сервис", "tourism"),
    ("Строительство и архитектура", "construction"),
    ("Транспорт и логистика", "transport"),
    ("Медиа и коммуникации", "media"),
    ("Другое", "other"),
]

INTEREST_KEYWORDS: list[tuple[str, tuple[str, ...], str]] = [
    ("education", ("дет", "ребен", "ребён", "работа с детьми", "люблю детей", "объясн", "учить", "учител", "помогать учиться", "школ", "детский сад", "воспитател", "педагог", "наставник", "кружк", "занятия с детьми", "развитие детей", "дошколь", "младшие классы", "начальные классы", "вожат"), "интерес к обучению, объяснению и работе с детьми"),
    ("jewelry", ("ювелир", "украшен", "драгоцен", "работа с метал", "кольц", "серьг", "дизайн украш", "ювелирное дело", "ручная работа", "издел", "камн", "огран", "часы", "часами"), "интерес к ювелирному делу, ручной работе и декоративным изделиям"),
    ("it", ("матем", "информ", "код", "программ", "игр", "компьют", "данн", "нейро", "техник", "хак", "пентест", "кибер", "сети", "админ"), "интерес к компьютерам, логике и технологиям"),
    ("design", ("рис", "дизайн", "арт", "фото", "творч", "визуал", "одеж", "мода"), "интерес к визуалу, творчеству и созданию образов"),
    ("medicine", ("биолог", "мед", "здоров", "леч", "пациент", "больниц", "сестрин", "фарма", "врач", "социаль"), "желание помогать людям и интерес к здоровью"),
    ("law", ("право", "безопас", "полици", "закон", "защит"), "интерес к правилам, безопасности и защите людей"),
    ("finance", ("эконом", "деньг", "банк", "счит", "аналит"), "интерес к цифрам, деньгам и анализу"),
    ("tourism", ("сервис", "туризм", "отел", "гост", "общаться"), "интерес к сервису, общению и организации"),
    ("construction", ("стро", "архит", "инжен", "черт", "робот", "механ", "свар"), "интерес к технике, инженерии и реальным объектам"),
    ("transport", ("транспорт", "логист", "поезд", "метро", "перевоз"), "интерес к транспорту, маршрутам и логистике"),
    ("media", ("медиа", "кино", "анимац", "видео", "звук", "съем", "съём"), "интерес к контенту, видео, звуку и коммуникациям"),
]

CYBER_QUERY_TERMS = (
    "хак",
    "хакер",
    "хакинг",
    "пентест",
    "кибербез",
    "кибер безопасность",
    "кибербезопасность",
    "информационная безопасность",
    "защита информации",
    "безопасность сет",
    "администрирование",
    "сетевое администрирование",
)

CYBER_SPECIALTY_MARKERS = (
    "информационной безопасности",
    "сетевое и системное администрирование",
    "компьютерные системы",
    "программным обеспечением",
    "веб-разработка",
)

EDUCATION_PRIORITY_MARKERS = (
    "дошкольное образование",
    "специальное дошкольное образование",
    "преподавание в начальных классах",
    "коррекционная педагогика в начальном образовании",
    "педагогика дополнительного образования",
)

EDUCATION_SECONDARY_MARKERS = (
    "физическая культура",
    "адаптивная физическая культура",
    "социальная работа",
)

EDUCATION_EXCLUDE_WITHOUT_CONTEXT = (
    "вокал",
    "музык",
    "дизайн",
    "творч",
    "информацион",
    "программ",
)

MUSIC_CONTEXT_MARKERS = (
    "музык",
    "пение",
    "вокал",
    "сцена",
    "хор",
)

JEWELRY_QUERY_TERMS = (
    "ювелир",
    "ювелирное дело",
    "украшен",
    "драгоцен",
    "кольц",
    "серьг",
    "дизайн украш",
    "работа с метал",
    "камн",
    "огран",
)

JEWELRY_SPECIALTY_MARKERS = (
    "ювелир",
    "технология обработки алмазов",
    "декоративно-прикладное искусство",
    "реставрация",
)

CONSTRUCTION_EXCLUDE_WITHOUT_CONTEXT = (
    "сетевое и системное администрирование",
    "компьютерные системы",
    "программ",
    "информационной безопасности",
    "веб-разработка",
)


@dataclass(slots=True)
class ScenarioAnswer:
    session_id: str
    answer: str
    dialog_mode: str
    route: str | None
    step: str | None
    suggestions: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "answer": self.answer,
            "dialog_mode": self.dialog_mode,
            "route": self.route,
            "step": self.step,
            "suggestions": self.suggestions,
            "suggestion_labels": self.suggestions,
            "suggestion_buttons": suggestion_buttons(
                self.suggestions,
                route=self.route,
                step=self.step,
            ),
        }


def normalize_label(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower().replace("ё", "е").strip()
    text = re.sub(r"[^\w\s№.-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


ADMISSION_LABEL_TO_SLUG = {normalize_label(label): slug for slug, label, _ in ADMISSION_TOPICS}


def action_for_label(label: str, *, route: str | None = None, step: str | None = None) -> str:
    _ = step
    normalized = normalize_label(label)

    numbered = re.match(r"^(\d+)\.\s*(?:подробнее|выбрать|вариант)", normalized)
    if numbered:
        return f"pick:{numbered.group(1)}"

    match = re.search(r"(?:подробнее про|выбрать)\s+(\d+)\s+(?:вариант|специальность|направление)", normalized)
    if match:
        return f"pick:{match.group(1)}"

    if normalized == normalize_label(PARENT_LABEL):
        return "set_user_type_parent"
    if normalized == normalize_label(APPLICANT_LABEL):
        return "set_user_type_applicant"

    if normalized in ADMISSION_LABEL_TO_SLUG:
        return f"admission_topic:{ADMISSION_LABEL_TO_SLUG[normalized]}"

    for industry_label, key in INDUSTRY_BUTTONS:
        if normalized == normalize_label(industry_label):
            return f"industry:{key}"

    label_actions = {
        "главное меню": "main_menu",
        "назад": "back",
        "завершить сессию": "end_session",
        "закончить сессию": "end_session",
        "выбрать колледж": "route_college",
        "найти конкретный колледж": "find_college",
        "помочь выбрать колледж": "help_choose_college",
        "контакты и адреса": "college_contacts",
        "все специальности": "college_specialties",
        "порядок поступления": "college_admission",
        "задать вопрос про этот колледж": "college_question",
        "новый поиск": "new_search",
        "да специальность выбрана": "college_specialty_yes",
        "нет еще выбираю": "college_specialty_no",
        "не знаю с чего начать": "college_specialty_unknown",
        "показать еще колледжи": "show_more_colleges",
        "выбрать профессию": "route_profession",
        "выбрать специальность": "route_profession",
        "выбрать отрасль": "choose_industry",
        "я знаю профессию": "know_profession",
        "я не знаю что выбрать": "unknown_profession",
        "подобрать по моим интересам": "profession_industry_interest",
        "показать колледжи": "show_colleges",
        "выбрать другую отрасль": "choose_industry",
        "изменить специальность": "know_profession",
        "изменить профессию": "know_profession",
        "изменить запрос": "know_profession",
        "уточнить интересы": "unknown_profession",
        "показать еще специальности": "show_more_specialties",
        "узнать о порядке поступления": "route_admission",
        "поступление": "route_admission",
        "другой вопрос про поступление": "other_admission_question",
        "контакты колледжа": "route_college",
        "свой вопрос": "route_custom",
    }
    if normalized == "показать еще":
        return "show_more_colleges" if route == "college" else "show_more_specialties"
    if normalized in label_actions:
        return label_actions[normalized]

    return re.sub(r"\W+", "_", normalized).strip("_") or "noop"


def suggestion_buttons(
    labels: list[str] | tuple[str, ...],
    *,
    route: str | None,
    step: str | None,
) -> list[dict[str, str]]:
    return [
        {
            "label": str(label),
            "action": action_for_label(str(label), route=route, step=step),
        }
        for label in labels
        if str(label).strip()
    ]


class ScenarioService:
    def __init__(
        self,
        chat_service: ChatService | None = None,
        session_service: SessionService | None = None,
    ) -> None:
        self.chat_service = chat_service or ChatService()
        self.session_service = session_service or self.chat_service.session_service

    def ask(
        self,
        db: Session,
        user_id: str,
        message: str,
        session_id: str | None = None,
        *,
        route: str | None = None,
        action: str | None = None,
        user_type: str | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        session = self.session_service.get_or_create_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
        )
        state = self.session_service.get_route_state(session)

        message = (message or "").strip()
        from_callback = action is not None
        action_code = self.resolve_action(message=message, route=route, action=action)
        requested_type = self.normalize_user_type(user_type) or self.user_type_from_message(message)

        if action_code in {"set_parent", "set_applicant"}:
            requested_type = "parent" if action_code == "set_parent" else "applicant"

        if requested_type and state.get("user_type") != requested_type:
            state = self.session_service.update_route_state(
                db,
                session,
                {
                    "user_type": requested_type,
                    "tone_mode": requested_type,
                    "current_route": "main_menu",
                    "route_step": "main_menu",
                },
            )
            role_only_message = self.user_type_from_message(message) is not None or normalize_label(message) in {"start", "начать"}
            if action_code in {"set_parent", "set_applicant"} or (not route and not action and role_only_message):
                answer = self.main_menu_text(state, first_time=True)
                return self.save_direct(
                    db,
                    session,
                    "" if from_callback else message or self.user_type_label(requested_type),
                    answer,
                    "main_menu",
                    MAIN_MENU,
                ).as_dict()

        if not state.get("user_type"):
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "user_type", "route_step": "choose_user_type"},
            )
            answer = self.user_type_prompt()
            return self.save_direct(
                db,
                session,
                message,
                answer,
                "user_type",
                USER_TYPE_BUTTONS,
            ).as_dict()

        if action_code == "main_menu":
            state = self.session_service.update_route_state(
                db,
                session,
                {
                    "current_route": "main_menu",
                    "route_step": "main_menu",
                },
            )
            return self.save_direct(
                db,
                session,
                message,
                self.main_menu_text(state),
                "main_menu",
                MAIN_MENU,
            ).as_dict()

        if action_code == "back":
            return self.handle_back(db, session, state, message).as_dict()

        if action_code.startswith("college_") or route == "college" or state.get("current_route") == "college":
            return self.handle_college(db, session, state, message, action_code).as_dict()

        if action_code.startswith("profession_") or action_code.startswith(("industry_", "industry:")) or route == "profession" or state.get("current_route") == "profession":
            return self.handle_profession(db, session, state, message, action_code).as_dict()

        if action_code.startswith(("admission_", "admission_topic:")) or route == "admission" or state.get("current_route") == "admission":
            return self.handle_admission(db, session, state, message, action_code, top_k=top_k).as_dict()

        if action_code.startswith("custom_") or route == "custom" or state.get("current_route") == "custom":
            return self.handle_custom(db, session, state, message, action_code, top_k=top_k).as_dict()

        # Backward-compatible old client path: do not drop into unrestricted chat;
        # route the message to a scenario when possible.
        return self.route_free_message(db, session, state, message, top_k=top_k).as_dict()

    def resolve_action(self, *, message: str, route: str | None, action: str | None) -> str:
        raw_action = (action or "").strip().lower()
        if raw_action.startswith(("industry:", "pick:", "admission_topic:")):
            return raw_action
        details_match = re.match(r"details_(\d+)$", raw_action)
        if details_match:
            return f"pick:{details_match.group(1)}"

        raw = normalize_label(action)
        label = normalize_label(message)

        if raw_action == "select_industry":
            for industry_label, key in INDUSTRY_BUTTONS:
                if label == normalize_label(industry_label):
                    return f"industry:{key}"

        explicit_actions = {
            "set_user_type_parent": "set_parent",
            "parent": "set_parent",
            "set_user_type_applicant": "set_applicant",
            "applicant": "set_applicant",
            "main_menu": "main_menu",
            "route_college": "college_start",
            "search_college": "college_search",
            "find_college": "college_find",
            "help_choose_college": "college_help",
            "college_specialty_yes": "college_specialty_yes",
            "college_specialty_no": "college_specialty_no",
            "college_specialty_unknown": "college_specialty_unknown",
            "college_contacts": "college_contacts",
            "college_specialties": "college_specialties",
            "college_admission": "college_admission",
            "college_question": "college_question",
            "new_search": "college_new_search",
            "show_more_colleges": "college_more_results",
            "route_profession": "profession_start",
            "choose_industry": "profession_choose_industry",
            "know_profession": "profession_know",
            "unknown_profession": "profession_unknown",
            "profession_industry_interest": "profession_industry_interest",
            "show_colleges": "profession_show_colleges",
            "show_more_specialties": "profession_more_specialties",
            "choose_another_industry": "profession_choose_industry",
            "route_admission": "admission_start",
            "other_admission_question": "admission_other",
            "route_custom": "custom_start",
            "back": "back",
            "end_session": "end_session",
        }
        if raw in explicit_actions:
            return explicit_actions[raw]

        if route and not action and not message.strip():
            route_map = {
                "college": "college_start",
                "profession": "profession_start",
                "admission": "admission_start",
                "custom": "custom_start",
            }
            if route in route_map:
                return route_map[route]

        label_actions = {
            normalize_label(PARENT_LABEL): "set_parent",
            normalize_label(APPLICANT_LABEL): "set_applicant",
            "главное меню": "main_menu",
            "выбрать колледж": "college_start",
            "найти конкретный колледж": "college_find",
            "помочь выбрать колледж": "college_help",
            "контакты и адреса": "college_contacts",
            "все специальности": "college_specialties",
            "порядок поступления": "college_admission",
            "задать вопрос про этот колледж": "college_question",
            "новый поиск": "college_new_search",
            "да специальность выбрана": "college_specialty_yes",
            "нет еще выбираю": "college_specialty_no",
            "не знаю с чего начать": "college_specialty_unknown",
            "показать еще колледжи": "college_more_results",
            "показать еще варианты": "college_more_results",
            "выбрать профессию": "profession_start",
            "выбрать специальность": "profession_start",
            "выбрать отрасль": "profession_choose_industry",
            "я знаю профессию": "profession_know",
            "я не знаю что выбрать": "profession_unknown",
            "подобрать по моим интересам": "profession_industry_interest",
            "показать колледжи": "profession_show_colleges",
            "выбрать другую отрасль": "profession_choose_industry",
            "показать еще": "profession_more_specialties",
            "показать еще специальности": "profession_more_specialties",
            "изменить профессию": "profession_know",
            "изменить специальность": "profession_know",
            "изменить запрос": "profession_know",
            "уточнить интересы": "profession_unknown",
            "узнать о порядке поступления": "admission_start",
            "поступление": "admission_start",
            "другой вопрос про поступление": "admission_other",
            "контакты колледжа": "college_start",
            "свой вопрос": "custom_start",
            "назад": "back",
        }
        if label in label_actions:
            return label_actions[label]

        if label in ADMISSION_LABEL_TO_SLUG:
            return f"admission_topic:{ADMISSION_LABEL_TO_SLUG[label]}"

        for industry_label, key in INDUSTRY_BUTTONS:
            if label == normalize_label(industry_label):
                return f"industry:{key}"

        numbered = re.match(r"^(\d+)\.\s*(?:подробнее|выбрать|вариант)", label)
        if numbered:
            return f"pick:{numbered.group(1)}"

        match = re.search(r"(?:подробнее про|выбрать)\s+(\d+)\s+(?:вариант|специальность|направление)", label)
        if match:
            return f"pick:{match.group(1)}"

        return raw

    def normalize_user_type(self, value: str | None) -> str | None:
        normalized = normalize_label(value)
        if normalized in {"parent", "родитель"}:
            return "parent"
        if normalized in {"applicant", "абитуриент", "поступающий", "абитуриент поступающий"}:
            return "applicant"
        return None

    def user_type_from_message(self, message: str) -> str | None:
        normalized = normalize_label(message)
        if normalized == normalize_label(PARENT_LABEL):
            return "parent"
        if normalized == normalize_label(APPLICANT_LABEL):
            return "applicant"
        return None

    def user_type_label(self, user_type: str) -> str:
        return PARENT_LABEL if user_type == "parent" else APPLICANT_LABEL

    def user_type_prompt(self) -> str:
        return (
            "Я помогу с колледжами Москвы, специальностями, профессиями и поступлением.\n\n"
            "Кто вы?"
        )

    def main_menu_text(self, state: dict[str, Any], *, first_time: bool = False) -> str:
        if state.get("user_type") == "parent":
            if first_time:
                return (
                    "Здравствуйте!\n\n"
                    "Я помогу сориентироваться в колледжах Москвы, специальностях и вопросах поступления.\n"
                    "Выберите, с чего удобнее начать."
                )
            prefix = "Главное меню. Выберите, с чего удобнее продолжить."
        else:
            if first_time:
                return (
                    "Привет!\n\n"
                    "Давай помогу тебе выбрать следующую ступень своего будущего.\n"
                    "Для начала давай определимся, что мы с тобой обсудим."
                )
            prefix = "Главное меню. Что хочешь сделать дальше?"
        return (
            f"{prefix}\n\n"
            "Выберите один из разделов ниже."
        )

    def handle_back(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        route = state.get("current_route")
        step = state.get("route_step")

        if route == "college":
            if step in {"awaiting_college_name", "college_choose_start", "awaiting_specialty_for_colleges"}:
                return self.college_start(db, session, state, message)
            if step in {"college_contacts", "college_specialties", "college_answer"} and state.get("last_college"):
                self.session_service.update_route_state(db, session, {"current_route": "college", "route_step": "college_found"})
                return self.save_direct(db, session, message, self.render_college_found(db, str(state["last_college"])), "college", COLLEGE_FOUND_BUTTONS)
            return self.save_direct(db, session, message, self.main_menu_text(state), "main_menu", MAIN_MENU)

        if route == "profession":
            if step in {"choose_industry", "awaiting_profession", "awaiting_interests"}:
                return self.profession_start(db, session, state, message)
            if step in {"industry_specialties", "direction_options"}:
                return self.industry_buttons(db, session, state, message)
            return self.save_direct(db, session, message, self.main_menu_text(state), "main_menu", MAIN_MENU)

        if route == "admission":
            if step in {"awaiting_admission_question", "admission_answer"}:
                return self.admission_start(db, session, state, message)
            return self.save_direct(db, session, message, self.main_menu_text(state), "main_menu", MAIN_MENU)

        return self.save_direct(db, session, message, self.main_menu_text(state), "main_menu", MAIN_MENU)

    def save_direct(
        self,
        db: Session,
        session,
        user_message: str,
        answer: str,
        dialog_mode: str,
        suggestions: list[str],
    ) -> ScenarioAnswer:
        state = self.session_service.get_route_state(session)
        answer = self.prepare_answer(answer, state)
        self.session_service.update_route_state(db, session, {"last_answer": answer})
        if user_message:
            self.session_service.add_message(db=db, session=session, role="user", content=user_message)
        self.session_service.add_message(db=db, session=session, role="assistant", content=answer)
        state = self.session_service.get_route_state(session)
        return ScenarioAnswer(
            session_id=session.session_id,
            answer=answer,
            dialog_mode=dialog_mode,
            route=state.get("current_route"),
            step=state.get("route_step"),
            suggestions=suggestions,
        )

    def prepare_answer(self, answer: str, state: dict[str, Any]) -> str:
        answer = re.sub(r"\*\*(.+?)\*\*", r"\1", answer or "")
        answer = re.sub(r"__(.+?)__", r"\1", answer)
        answer = re.sub(r"\n{3,}", "\n\n", answer).strip()
        if state.get("tone_mode") == "parent":
            answer = self.apply_parent_tone(answer)
        return answer

    def apply_parent_tone(self, text: str) -> str:
        replacements = [
            (r"\bтебе\b", "вам"),
            (r"\bтебя\b", "вас"),
            (r"\bтобой\b", "вами"),
            (r"\bты\b", "вы"),
            (r"\bтвой\b", "ваш"),
            (r"\bтвоя\b", "ваша"),
            (r"\bтвое\b", "ваше"),
            (r"\bтвоё\b", "ваше"),
            (r"\bтвои\b", "ваши"),
            (r"\bхочешь\b", "хотите"),
            (r"\bможешь\b", "можете"),
            (r"\bзнаешь\b", "знаете"),
            (r"\bвыбрал\b", "выбрали"),
            (r"\bвыбрала\b", "выбрали"),
            (r"\bнапиши\b", "напишите"),
            (r"\bрасскажи\b", "расскажите"),
            (r"\bответь\b", "ответьте"),
        ]
        result = text
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def handle_college(self, db: Session, session, state: dict[str, Any], message: str, action_code: str) -> ScenarioAnswer:
        step = state.get("route_step")

        if action_code in {"college_start", ""} and state.get("current_route") != "college":
            return self.college_start(db, session, state, message)

        if action_code in {"college_start"}:
            return self.college_start(db, session, state, message)

        if action_code in {"college_find", "college_new_search"}:
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "college", "route_step": "awaiting_college_name"},
            )
            return self.save_direct(
                db,
                session,
                message,
                "Введите название колледжа или часть названия. Например: КАИТ 20, МПК, Красина, ИТ.Москва.",
                "college",
                [BACK_BUTTON, MAIN_MENU_BUTTON],
            )

        if action_code == "college_help":
            return self.college_help_start(db, session, state, message)

        if action_code == "college_specialty_yes":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "college", "route_step": "awaiting_specialty_for_colleges"},
            )
            return self.save_direct(
                db,
                session,
                message,
                "Введите название специальности или направление. Например: графический дизайнер, программирование, педагогика, фотография.",
                "college",
                [BACK_BUTTON, MAIN_MENU_BUTTON],
            )

        if action_code == "college_specialty_no":
            return self.profession_start(db, session, state, message)

        if action_code == "college_specialty_unknown":
            return self.profession_unknown_prompt(db, session, state, message)

        if action_code == "college_contacts":
            return self.college_contacts(db, session, state, message)

        if action_code == "college_specialties":
            return self.college_specialties(db, session, state, message)

        if action_code == "college_admission":
            return self.admission_start(db, session, state, message)

        if action_code == "college_question":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "college", "route_step": "awaiting_college_question"},
            )
            college = state.get("last_college")
            prompt = "Напишите вопрос про этот колледж."
            if college:
                prompt = f"Напишите вопрос про колледж «{college}»."
            return self.save_direct(db, session, message, prompt, "college", [BACK_BUTTON, MAIN_MENU_BUTTON])

        if action_code == "college_more_results":
            return self.render_more_college_results(db, session, state, message)

        if action_code.startswith("pick:"):
            return self.pick_result_item(db, session, state, message, action_code)

        if action_code == "college_search" or step == "awaiting_college_name":
            return self.search_college(db, session, state, message)

        if step == "awaiting_specialty_for_colleges":
            return self.show_colleges_for_query(db, session, state, message, message)

        if step == "awaiting_college_question":
            college = state.get("last_college")
            query = f"{college}. {message}" if college else message
            return self.call_chat_service(
                db,
                session,
                state,
                query,
                original_message=message,
                route_updates={"current_route": "college", "route_step": "college_answer"},
                suggestions=COLLEGE_FOUND_BUTTONS if college else MAIN_MENU,
                top_k=5,
            )

        return self.college_start(db, session, state, message)

    def college_start(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        user_type = state.get("user_type")
        question = (
            "Вы хотите найти конкретный колледж или помочь выбрать подходящий колледж?"
            if user_type == "parent"
            else "Ты уже знаешь колледж, который хочешь посмотреть, или хочешь, чтобы я помог выбрать?"
        )
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "college", "route_step": "college_start"},
        )
        return self.save_direct(db, session, message, question, "college", COLLEGE_START_BUTTONS)

    def college_help_start(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        question = (
            "Вы уже выбрали специальность или направление обучения?"
            if state.get("user_type") == "parent"
            else "Ты уже выбрал специальность или пока не знаешь?"
        )
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "college", "route_step": "college_choose_start"},
        )
        return self.save_direct(db, session, message, question, "college", COLLEGE_CHOOSE_BUTTONS)

    def search_college(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        college = self.chat_service.canonical_college_from_db(db, message) or self.chat_service.canonical_college_from_text(message)
        if not college:
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "college", "route_step": "college_not_found"},
            )
            answer = (
                "Я не нашёл такой колледж в своей базе. Попробуйте написать название иначе "
                f"или проверьте список колледжей в Атласе профессий: {ATLAS_URL}"
            )
            return self.save_direct(db, session, message, answer, "college", ["Новый поиск", BACK_BUTTON, MAIN_MENU_BUTTON])

        answer = self.render_college_found(db, college)
        self.session_service.update_route_state(
            db,
            session,
            {
                "current_route": "college",
                "route_step": "college_found",
                "last_college": college,
                "last_results": [],
            },
        )
        return self.save_direct(db, session, message, answer, "college", COLLEGE_FOUND_BUTTONS)

    def render_college_found(self, db: Session, college: str) -> str:
        card = self.chat_service.get_college_card_for_name(db, college)
        display_name = self.chat_service.extract_college_name(card) if card else college
        brief = self.brief_from_doc(card) if card else ""

        lines = [display_name, ""]
        if brief:
            lines.extend(["Кратко:", brief, ""])
        lines.extend(
            [
                "Что можно посмотреть:",
                "- контакты и адреса",
                "- все специальности",
                "- порядок поступления",
                "- задать вопрос про этот колледж",
            ]
        )
        return "\n".join(lines).strip()

    def brief_from_doc(self, doc: Document | None) -> str:
        if not doc or not doc.content:
            return ""
        text = re.sub(r"\s+", " ", doc.content).strip()
        text = re.sub(r"https?://\S+", "", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        brief = " ".join(sentence for sentence in sentences[:2] if sentence)
        return brief[:360].strip()

    def college_contacts(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        college = state.get("last_college")
        if not college:
            return self.save_direct(
                db,
                session,
                message,
                "Сначала выберите или найдите колледж.",
                "college",
                ["Новый поиск", "Главное меню"],
            )
        answer = self.chat_service.render_college_contacts(db, str(college), "контакты и адреса")
        self.session_service.update_route_state(db, session, {"current_route": "college", "route_step": "college_contacts"})
        return self.save_direct(db, session, message, answer, "college", COLLEGE_FOUND_BUTTONS)

    def college_specialties(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        college = state.get("last_college")
        if not college:
            return self.save_direct(
                db,
                session,
                message,
                "Сначала выберите или найдите колледж.",
                "college",
                ["Новый поиск", "Главное меню"],
            )
        answer = self.chat_service.render_all_specialties_for_college(db, str(college))
        self.session_service.update_route_state(db, session, {"current_route": "college", "route_step": "college_specialties"})
        return self.save_direct(db, session, message, answer, "college", COLLEGE_FOUND_BUTTONS)

    def show_colleges_for_query(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        user_message: str,
        query: str,
    ) -> ScenarioAnswer:
        items = self.find_college_options(db, query)
        if not items:
            self.session_service.update_route_state(
                db,
                session,
                {
                    "current_route": "college",
                    "route_step": "college_results_empty",
                    "last_specialty": query,
                    "last_results": [],
                },
            )
            answer = (
                "Я не нашёл колледжи по этой специальности в своей базе. "
                f"Попробуйте написать направление иначе или проверьте Атлас профессий: {ATLAS_URL}"
            )
            return self.save_direct(db, session, user_message, answer, "college", ["Изменить специальность", BACK_BUTTON, MAIN_MENU_BUTTON])

        state_updates = {
            "current_route": "college",
            "route_step": "college_results",
            "last_specialty": query,
            "last_results": {
                "kind": "college_options",
                "query": query,
                "items": items,
                "offset": 0,
            },
        }
        self.session_service.update_route_state(db, session, state_updates)
        title = "Вот колледжи, где есть эта специальность или близкие варианты:"
        if len(items) == 1:
            title = "В моей базе по этой специальности найден один колледж:"
        return self.render_college_results_page(db, session, user_message, title)

    def render_more_college_results(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        last_results = state.get("last_results") if isinstance(state.get("last_results"), dict) else {}
        if last_results.get("kind") != "college_options":
            return self.save_direct(
                db,
                session,
                message,
                "Сначала нужно выполнить поиск колледжей по специальности.",
                "college",
                ["Помочь выбрать колледж", MAIN_MENU_BUTTON],
            )
        return self.render_college_results_page(db, session, message, "Показываю ещё колледжи из найденных вариантов:")

    def render_college_results_page(self, db: Session, session, user_message: str, title: str) -> ScenarioAnswer:
        state = self.session_service.get_route_state(session)
        last_results = state.get("last_results") if isinstance(state.get("last_results"), dict) else {}
        items = last_results.get("items", [])
        offset = int(last_results.get("offset") or 0)
        page = [item for item in items[offset : offset + 3] if isinstance(item, dict)]
        if not page:
            return self.save_direct(
                db,
                session,
                user_message,
                "Больше подходящих колледжей в моей базе не нашёл. Можно изменить специальность или выбрать другой раздел.",
                "college",
                ["Изменить специальность", MAIN_MENU_BUTTON],
            )

        lines = [title]
        for idx, item in enumerate(page, start=offset + 1):
            lines.append("")
            lines.append(f"{idx}. Колледж: {item.get('college', '')}")
            lines.append(f"   Специальность: {item.get('specialty', '')}")
            professions = item.get("professions") or []
            if professions:
                lines.append(f"   После обучения: {', '.join(str(p) for p in professions[:3])}")
            website = str(item.get("website") or "").strip()
            if website:
                lines.append(f"   Сайт: {website}")

        new_offset = offset + len(page)
        last_results = dict(last_results)
        last_results["offset"] = new_offset
        self.session_service.update_route_state(db, session, {"last_results": last_results})

        suggestions: list[str] = []
        if new_offset < len(items):
            suggestions.append("Показать ещё колледжи")
        suggestions.extend([f"{idx}. Подробнее" for idx in range(offset + 1, offset + len(page) + 1)])
        suggestions.extend(["Изменить специальность", MAIN_MENU_BUTTON])
        return self.save_direct(db, session, user_message, "\n".join(lines), "college", suggestions)

    def pick_result_item(self, db: Session, session, state: dict[str, Any], message: str, action_code: str) -> ScenarioAnswer:
        number = int(action_code.split(":", 1)[1])
        last_results = state.get("last_results") if isinstance(state.get("last_results"), dict) else {}
        items = last_results.get("items", [])
        if not (1 <= number <= len(items)):
            return self.save_direct(db, session, message, "Не вижу такого номера в текущем списке.", "scenario", ["Главное меню"])

        item = items[number - 1]
        kind = last_results.get("kind")
        if kind == "college_options":
            college = str(item.get("college") or "").strip()
            if college:
                answer = self.render_college_found(db, college)
                self.session_service.update_route_state(
                    db,
                    session,
                    {
                        "current_route": "college",
                        "route_step": "college_found",
                        "last_college": college,
                        "last_specialty": item.get("specialty") or state.get("last_specialty"),
                    },
                )
                return self.save_direct(db, session, message, answer, "college", COLLEGE_FOUND_BUTTONS)

        if kind in {"specialty_options", "industry_specialties"}:
            specialty = str(item.get("specialty") or "").strip()
            if specialty:
                self.session_service.update_route_state(
                    db,
                    session,
                    {"last_specialty": specialty, "current_route": "profession", "route_step": "specialty_selected"},
                )
                return self.show_colleges_for_query(db, session, state, message, specialty)

        if kind == "direction_options":
            key = str(item.get("key") or "").strip()
            if key:
                return self.show_industry_specialties(db, session, state, message, key)

        return self.save_direct(db, session, message, "Не удалось открыть выбранный вариант.", "scenario", ["Главное меню"])

    def find_college_options(self, db: Session, query: str, *, limit: int = 15) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for doc in self.chat_service.find_specialty_docs_by_query(db, query):
            entry = self.entry_from_doc(doc)
            key = (self.chat_service.college_key(entry["college"]), normalize_label(entry["specialty"]))
            if key not in seen:
                seen.add(key)
                entries.append(entry)

        for match in self.chat_service.get_reference_catalog().match_professions(query, limit=3):
            for raw in match.colleges:
                entry = self.entry_from_catalog(raw)
                key = (self.chat_service.college_key(entry["college"]), normalize_label(entry["specialty"]))
                if entry["college"] and entry["specialty"] and key not in seen:
                    seen.add(key)
                    entries.append(entry)

        return entries[:limit]

    def entry_from_doc(self, doc: Document) -> dict[str, Any]:
        return {
            "college": self.chat_service.extract_college_name(doc),
            "specialty": self.chat_service.extract_specialty_name(doc),
            "professions": [str(item).strip() for item in (doc.metadata_json.get("professions") or []) if str(item).strip()],
            "website": str(doc.metadata_json.get("website") or "").strip(),
        }

    def entry_from_catalog(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "college": str(item.get("college") or "").strip(),
            "specialty": str(item.get("specialty") or "").strip(),
            "professions": [str(value).strip() for value in (item.get("professions") or []) if str(value).strip()],
            "website": str(item.get("website") or "").strip(),
        }

    def handle_profession(self, db: Session, session, state: dict[str, Any], message: str, action_code: str) -> ScenarioAnswer:
        step = state.get("route_step")

        if action_code in {"profession_start", ""} and state.get("current_route") != "profession":
            return self.profession_start(db, session, state, message)

        if action_code == "profession_start":
            return self.profession_start(db, session, state, message)

        if action_code == "profession_choose_industry":
            return self.industry_buttons(db, session, state, message)

        if action_code.startswith("industry:"):
            return self.show_industry_specialties(db, session, state, message, action_code.split(":", 1)[1])

        if action_code == "profession_know":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "profession", "route_step": "awaiting_profession"},
            )
            return self.save_direct(
                db,
                session,
                message,
                "Напишите профессию или направление. Например: программист, фотограф, педагог, дизайнер, специалист по информационной безопасности.",
                "profession",
                [BACK_BUTTON, MAIN_MENU_BUTTON],
            )

        if action_code == "profession_unknown":
            return self.profession_unknown_prompt(db, session, state, message)

        if action_code == "profession_industry_interest":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "profession", "route_step": "awaiting_industry_interest"},
            )
            return self.save_direct(
                db,
                session,
                message,
                (
                    "Расскажите, какие интересы есть у ребёнка в выбранной отрасли. Можно указать любимые предметы, хобби и желаемый формат работы."
                    if state.get("user_type") == "parent"
                    else "Расскажи, что тебе интересно в этой отрасли. Можно написать простыми словами: работа с детьми, дизайн, техника, код, помощь людям или что-то своё."
                ),
                "profession",
                [BACK_BUTTON, MAIN_MENU_BUTTON],
            )

        if action_code == "profession_show_colleges":
            specialty = state.get("last_specialty")
            if not specialty:
                return self.save_direct(
                    db,
                    session,
                    message,
                    "Сначала выберите специальность, а потом я покажу колледжи.",
                    "profession",
                    ["Выбрать отрасль", "Я знаю профессию", MAIN_MENU_BUTTON],
                )
            return self.show_colleges_for_query(db, session, state, message, str(specialty))

        if action_code == "profession_more_specialties":
            return self.render_more_specialties(db, session, state, message)

        if action_code.startswith("pick:"):
            return self.pick_result_item(db, session, state, message, action_code)

        if step == "awaiting_profession":
            return self.show_specialties_for_profession(db, session, state, message)

        if step == "awaiting_interests":
            return self.show_interest_directions(db, session, state, message)

        if step == "awaiting_industry_interest":
            industry = state.get("last_industry")
            query = f"{industry or ''}. {message}".strip()
            return self.show_specialties_for_profession(db, session, state, message, query=query)

        if step == "profession_start" and message:
            if self.looks_like_interest_description(message):
                return self.show_interest_directions(db, session, state, message)
            return self.show_specialties_for_profession(db, session, state, message)

        return self.profession_start(db, session, state, message)

    def profession_start(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "profession", "route_step": "profession_start"},
        )
        return self.save_direct(
            db,
            session,
            message,
            (
                "Выберите, как удобнее начать подбор направления для поступающего."
                if state.get("user_type") == "parent"
                else "Давай сначала выберем направление, а потом посмотрим колледжи. Как удобнее начать?"
            ),
            "profession",
            PROFESSION_START_BUTTONS,
        )

    def industry_buttons(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "profession", "route_step": "choose_industry"},
        )
        labels = [label for label, _ in INDUSTRY_BUTTONS]
        return self.save_direct(
            db,
            session,
            message,
            "Выберите отрасль:",
            "profession",
            labels + [BACK_BUTTON, MAIN_MENU_BUTTON],
        )

    def show_industry_specialties(self, db: Session, session, state: dict[str, Any], message: str, key: str) -> ScenarioAnswer:
        if key == "other":
            return self.profession_unknown_prompt(db, session, state, message)

        title, items = self.industry_specialty_options(db, key)
        if not items:
            return self.save_direct(
                db,
                session,
                message,
                "По этой отрасли пока не вижу готового списка специальностей. Напишите интересы свободно, и я попробую подобрать направление.",
                "profession",
                ["Я не знаю, что выбрать", BACK_BUTTON, MAIN_MENU_BUTTON],
            )

        self.session_service.update_route_state(
            db,
            session,
            {
                "current_route": "profession",
                "route_step": "industry_specialties",
                "last_industry": title,
                "last_results": {
                    "kind": "industry_specialties",
                    "query": title,
                    "items": items,
                    "offset": 0,
                },
            },
        )
        return self.render_specialty_options_page(
            db,
            session,
            message,
            f"В отрасли «{title}» могут подойти такие специальности:",
        )

    def industry_specialty_options(self, db: Session, key: str) -> tuple[str, list[dict[str, Any]]]:
        if key == "education":
            entries = self.education_specialty_entries(db)
            title = "Педагогика и работа с детьми"
        elif key == "jewelry":
            entries = self.jewelry_specialty_entries(db)
            title = "Ювелирное дело и декоративно-прикладное искусство"
        else:
            payload = self.chat_service.get_reference_catalog().industry_data().get("industries", {}).get(key, {})
            title = str(payload.get("title") or key)
            entries = [self.entry_from_catalog(item) for item in payload.get("college_specialties", []) if isinstance(item, dict)]

        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for entry in entries:
            specialty = str(entry.get("specialty") or "").strip()
            if not specialty:
                continue
            norm = normalize_label(specialty)
            if key == "construction" and any(marker in norm for marker in CONSTRUCTION_EXCLUDE_WITHOUT_CONTEXT):
                continue
            if norm in seen:
                continue
            seen.add(norm)
            professions = entry.get("professions") or []
            result.append(
                {
                    "specialty": specialty,
                    "why": self.specialty_why(specialty),
                    "professions": professions,
                }
            )
            if len(result) >= 8:
                break
        return title, result

    def jewelry_specialty_entries(self, db: Session) -> list[dict[str, Any]]:
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for doc in docs:
            entry = self.entry_from_doc(doc)
            haystack = normalize_label(
                " ".join(
                    [
                        entry.get("specialty", ""),
                        " ".join(str(value) for value in entry.get("professions", [])),
                        entry.get("college", ""),
                    ]
                )
            )
            if not any(marker in haystack for marker in JEWELRY_SPECIALTY_MARKERS):
                continue
            key = (self.chat_service.college_key(entry["college"]), normalize_label(entry["specialty"]))
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)

        if entries:
            return entries[:12]

        for profession in [
            "ювелир-закрепщик",
            "ювелир-монтировщик",
            "ювелир-огранщик природных камней",
            "эксперт-оценщик ювелирных изделий",
        ]:
            for match in self.chat_service.get_reference_catalog().match_professions(profession, limit=1):
                for raw in match.colleges:
                    entry = self.entry_from_catalog(raw)
                    key = (self.chat_service.college_key(entry["college"]), normalize_label(entry["specialty"]))
                    if entry["college"] and entry["specialty"] and key not in seen:
                        seen.add(key)
                        entries.append(entry)

        return entries[:12]

    def education_specialty_entries(self, db: Session) -> list[dict[str, Any]]:
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()
        entries: list[tuple[int, dict[str, Any]]] = []
        seen: set[tuple[str, str]] = set()

        for doc in docs:
            specialty = self.chat_service.extract_specialty_name(doc)
            norm = normalize_label(specialty)
            if not norm:
                continue
            if any(marker in norm for marker in EDUCATION_EXCLUDE_WITHOUT_CONTEXT):
                continue
            priority = self.education_priority(norm)
            if priority is None:
                continue

            entry = self.entry_from_doc(doc)
            key = (self.chat_service.college_key(entry["college"]), normalize_label(entry["specialty"]))
            if key in seen:
                continue
            seen.add(key)
            entries.append((priority, entry))

        entries.sort(key=lambda item: (item[0], normalize_label(item[1].get("specialty"))))
        if entries:
            return [entry for _, entry in entries[:16]]

        return self.find_college_options(db, "дошкольное образование преподавание начальных классах педагогика", limit=16)

    def education_priority(self, specialty_norm: str) -> int | None:
        for idx, marker in enumerate(EDUCATION_PRIORITY_MARKERS):
            if marker in specialty_norm:
                return idx
        for idx, marker in enumerate(EDUCATION_SECONDARY_MARKERS, start=len(EDUCATION_PRIORITY_MARKERS)):
            if marker in specialty_norm:
                return idx
        if "педагог" in specialty_norm or "образование" in specialty_norm:
            return len(EDUCATION_PRIORITY_MARKERS) + len(EDUCATION_SECONDARY_MARKERS)
        return None

    def specialty_why(self, specialty: str) -> str:
        q = normalize_label(specialty)
        if any(x in q for x in ["ювелир", "алмаз", "декоративно-приклад", "реставрац"]):
            return "если интересны украшения, ручная работа, материалы и точные ремесленные навыки"
        if any(x in q for x in ["разработка", "программ", "систем", "информацион"]):
            return "если интересны технологии, логика и цифровые продукты"
        if any(x in q for x in ["дизайн", "живоп", "фото", "творч", "анимац"]):
            return "если хочется создавать визуальные работы и проекты"
        if any(x in q for x in ["медицин", "сестрин", "фарма", "социаль"]):
            return "если важно помогать людям и разбираться в здоровье"
        if any(x in q for x in ["право", "безопас", "пожар", "поли"]):
            return "если интересны порядок, защита и безопасность"
        if any(x in q for x in ["педагог", "дошколь", "преподав"]):
            return "если нравится объяснять, поддерживать и работать с детьми"
        return "если направление совпадает с вашими интересами"

    def profession_unknown_prompt(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        prompt = (
            "Расскажите, какие интересы есть у ребёнка. Можно указать любимые предметы, хобби и желаемое направление. Я предложу подходящие варианты и объясню, что стоит проверить дополнительно."
            if state.get("user_type") == "parent"
            else "Расскажи, что тебе интересно. Можно написать простыми словами: любимые предметы, хобби, что получается лучше всего. Если пока не знаешь — ничего страшного, начнём с интересов."
        )
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "profession", "route_step": "awaiting_interests"},
        )
        return self.save_direct(db, session, message, prompt, "profession", [BACK_BUTTON, MAIN_MENU_BUTTON])

    def show_interest_directions(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        directions = self.infer_directions(message)
        if not directions:
            answer = (
                "Пока не могу уверенно отнести это к одной отрасли.\n\n"
                "Расскажите чуть подробнее: ребёнку ближе работа с людьми, детьми, техникой, творчеством, IT, медициной, правом, финансами, строительством или сервисом?"
                if state.get("user_type") == "parent"
                else "Пока не могу уверенно отнести это к одной отрасли.\n\n"
                "Напиши чуть подробнее: тебе ближе работа с людьми, детьми, техникой, творчеством, IT, медициной, правом, финансами, строительством или сервисом?"
            )
            return self.save_direct(db, session, message, answer, "profession", ["Уточнить интересы", "Выбрать отрасль", MAIN_MENU_BUTTON])

        items = []
        for key, why in directions:
            title, specialties = self.industry_specialty_options(db, key)
            examples = [item["specialty"] for item in specialties[:3]]
            items.append({"key": key, "title": title, "why": why, "examples": examples})

        self.session_service.update_route_state(
            db,
            session,
            {
                "current_route": "profession",
                "route_step": "direction_options",
                "last_results": {
                    "kind": "direction_options",
                    "query": message,
                    "items": items,
                    "offset": 0,
                },
            },
        )

        pronoun = "вашему описанию" if state.get("user_type") == "parent" else "твоему описанию"
        lines = [f"По {pronoun} могут подойти такие направления:"]
        for idx, item in enumerate(items, start=1):
            examples = ", ".join(item.get("examples") or [])
            lines.append("")
            lines.append(f"{idx}. Направление: {item['title']}")
            lines.append(f"   Почему может подойти: {item['why']}.")
            if examples:
                lines.append(f"   Примеры специальностей: {examples}")

        suggestions = [f"Выбрать {idx} направление" for idx in range(1, len(items) + 1)]
        suggestions.extend(["Уточнить интересы", MAIN_MENU_BUTTON])
        return self.save_direct(db, session, message, "\n".join(lines), "profession", suggestions)

    def infer_directions(self, text: str) -> list[tuple[str, str]]:
        q = normalize_label(text)
        found: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key, markers, why in INTEREST_KEYWORDS:
            if key in seen:
                continue
            if any(marker in q for marker in markers):
                found.append((key, why))
                seen.add(key)
            if len(found) >= 4:
                break
        return found[:4]

    def looks_like_interest_description(self, text: str) -> bool:
        q = normalize_label(text)
        return any(
            marker in q
            for marker in [
                "нрав",
                "любл",
                "интерес",
                "хобби",
                "получается",
                "работать",
                "заниматься",
                "предмет",
                "хочу помогать",
            ]
        )

    def is_cyber_query(self, text: str) -> bool:
        q = normalize_label(text)
        return any(term in q for term in CYBER_QUERY_TERMS)

    def is_jewelry_query(self, text: str) -> bool:
        q = normalize_label(text)
        return any(term in q for term in JEWELRY_QUERY_TERMS)

    def cyber_clarification_answer(self, state: dict[str, Any]) -> str:
        if state.get("user_type") == "parent":
            return (
                "Если речь о легальной кибербезопасности, можно рассмотреть направления, связанные с информационной безопасностью, сетями и программированием.\n\n"
                "Уточните, что ближе поступающему:\n"
                "- защита информации\n"
                "- сети и администрирование\n"
                "- программирование\n"
                "- анализ уязвимостей"
            )
        return (
            "Под хакингом могут иметь в виду разные вещи. Если речь про легальную кибербезопасность, можно смотреть направления по информационной безопасности, сетям и программированию.\n\n"
            "Уточни, что тебе ближе:\n"
            "- защита информации\n"
            "- сети и администрирование\n"
            "- программирование\n"
            "- анализ уязвимостей"
        )

    def has_svo_priority_query(self, text: str) -> bool:
        q = normalize_label(text)
        return any(
            marker in q
            for marker in [
                "сво",
                "участник сво",
                "дети участников",
                "мобилиз",
                "военнослуж",
                "добровол",
                "контрактник",
                "вдова",
                "вдовец",
            ]
        ) and any(marker in q for marker in ["льгот", "преимуществ", "первоочеред", "поступ", "зачисл"])

    def has_olympiad_benefit_query(self, text: str) -> bool:
        q = normalize_label(text)
        return any(marker in q for marker in ["олимпиад", "индивидуальн достижен"]) and any(
            marker in q for marker in ["преимуществ", "льгот", "поступ", "зачисл", "балл"]
        )

    def has_general_benefit_query(self, text: str) -> bool:
        q = normalize_label(text)
        return any(marker in q for marker in ["льгот", "преимуществ", "первоочеред", "приоритет"]) and any(
            marker in q for marker in ["поступ", "зачисл", "колледж"]
        )

    def has_ovz_exam_query(self, text: str) -> bool:
        q = normalize_label(text)
        has_ovz = any(marker in q for marker in ["овз", "инвалид", "особые услов", "специальные услов", "не могу сдавать", "не могу проходить"])
        has_exam = any(marker in q for marker in ["вступитель", "испытан", "экзам", "сдавать"])
        return has_ovz and has_exam

    def has_general_exam_query(self, text: str) -> bool:
        q = normalize_label(text)
        has_exam = any(marker in q for marker in ["вступитель", "испытан", "экзам", "ви "])
        return has_exam and not self.has_ovz_exam_query(text)

    def admission_topic_from_text(self, text: str) -> str | None:
        q = normalize_label(text)
        if q in ADMISSION_LABEL_TO_SLUG:
            return ADMISSION_LABEL_TO_SLUG[q]
        if self.has_svo_priority_query(text):
            return "svo_priority"
        if self.has_general_exam_query(text) or self.has_ovz_exam_query(text):
            return "ovz" if self.has_ovz_exam_query(text) else "exams"
        if any(marker in q for marker in ["овз", "инвалид", "специальные услов", "особые услов"]):
            return "ovz"
        if "документ" in q:
            return "documents"
        if any(marker in q for marker in ["арм", "отсроч", "военком", "призыв"]):
            return "army"
        if any(marker in q for marker in ["срок", "когда", "до какого", "последний день"]):
            return "deadlines"
        if any(marker in q for marker in ["бюджет", "конкурс", "мест"]):
            return "budget"
        if any(marker in q for marker in ["заявлен", "подать", "mos.ru", "мос.ру"]):
            return "application"
        return None

    def related_admission_labels(self, topic: str | None) -> list[str]:
        if not topic:
            return []
        return list(ADMISSION_RELATED_TOPICS.get(topic, []))

    def admission_suggestions(self, topic: str | None) -> list[str]:
        suggestions = self.related_admission_labels(topic)
        suggestions.extend(["Другой вопрос про поступление", MAIN_MENU_BUTTON])
        return suggestions

    def append_related_admission_topics(self, answer: str, topic: str | None) -> str:
        labels = self.related_admission_labels(topic)
        if not labels:
            return answer
        lines = [answer.rstrip(), "", "Можно ещё посмотреть:"]
        for label in labels:
            lines.append(f"- {label}")
        return "\n".join(lines)

    def render_general_exams_answer(self, state: dict[str, Any]) -> str:
        if state.get("user_type") == "parent":
            return (
                "В моей базе нет полного перечня вступительных испытаний по всем колледжам и специальностям.\n\n"
                "Условия могут зависеть от конкретного колледжа и выбранной специальности. "
                "Я могу помочь подобрать колледж или специальность, а затем дать сайт и контакты приёмной комиссии, где лучше уточнить вступительные испытания."
            )
        return (
            "В моей базе нет полного списка вступительных испытаний по всем колледжам и специальностям.\n\n"
            "Обычно такие условия зависят от конкретного колледжа и специальности. "
            "Я могу помочь выбрать колледж или специальность, а потом дать сайт и контакты, где можно проверить вступительные испытания."
        )

    def render_svo_priority_answer(self, state: dict[str, Any]) -> str:
        prefix = (
            "В базе есть информация о первоочередном праве зачисления для отдельных категорий."
        )
        lines = [
            prefix,
            "",
            "Кратко:",
            "первоочередное право может относиться к отдельным участникам СВО, военнослужащим, мобилизованным, добровольцам, некоторым членам их семей, а также другим категориям, указанным в ч. 5.1 ст. 71 Закона об образовании.",
            "",
            "Важно:",
            "- статус и категорию нужно подтверждать официальными документами",
            "- точный перечень документов лучше уточнить в приёмной комиссии колледжа",
            "- правила приёма нужно перепроверить для конкретного года и колледжа",
        ]
        if state.get("user_type") == "parent":
            lines.append("")
            lines.append("По одному сообщению нельзя точно подтвердить, относится ли ваша ситуация к этой категории. Рекомендую уточнить статус и перечень документов в приёмной комиссии выбранного колледжа.")
        else:
            lines.append("")
            lines.append("По одному сообщению я не смогу точно сказать, положено ли преимущество именно в твоей ситуации. Лучше проверить это в приёмной комиссии колледжа.")
        return "\n".join(lines)

    def render_olympiad_benefit_answer(self, state: dict[str, Any]) -> str:
        if state.get("user_type") == "parent":
            return (
                "Теперь про олимпиады:\n"
                "В моей базе нет подтверждения, что участие в олимпиадах автоматически даёт преимущество при поступлении в колледж. "
                "Эту часть лучше уточнить в правилах приёма конкретного колледжа или в приёмной комиссии."
            )
        return (
            "А теперь про олимпиады:\n"
            "В моей базе нет подтверждения, что участие в олимпиадах автоматически даёт преимущество при поступлении в колледж. "
            "Лучше проверить правила приёма конкретного колледжа или спросить в приёмной комиссии."
        )

    def render_multi_intent_answer(
        self,
        db: Session,
        state: dict[str, Any],
        message: str,
        *,
        college: str | None,
    ) -> str | None:
        q = normalize_label(message)
        has_pedagogy = any(marker in q for marker in ["педагог", "учитель", "дошколь", "дет"])
        has_college = college is not None
        has_benefit = self.has_svo_priority_query(message) or self.has_olympiad_benefit_query(message) or self.has_general_benefit_query(message)
        if not has_benefit or not (has_college or has_pedagogy):
            return None

        user_is_parent = state.get("user_type") == "parent"
        intro = (
            "Я понял несколько тем в вашем вопросе:"
            if user_is_parent
            else "Я вижу тут несколько тем:"
        )
        themes = []
        if has_college:
            themes.append(f"про {college}")
        if has_pedagogy:
            themes.append("про педагогику")
        if self.has_svo_priority_query(message):
            themes.append("про первоочередное право или льготы")
        elif self.has_olympiad_benefit_query(message):
            themes.append("про преимущества из-за олимпиад")
        else:
            themes.append("про преимущества при поступлении")

        lines = [f"{intro} {', '.join(themes)}.", ""]
        if user_is_parent:
            lines.append("Сначала про колледж и направление:")
        else:
            lines.append("Сначала разберём колледж и направление:")
        lines.extend(self.render_primary_multi_intent_block(db, college=college, has_pedagogy=has_pedagogy))

        lines.append("")
        if self.has_svo_priority_query(message):
            lines.append("Теперь про СВО и первоочередное право:")
            lines.append(self.render_svo_priority_answer(state))
        elif self.has_olympiad_benefit_query(message):
            lines.append(self.render_olympiad_benefit_answer(state))
        else:
            lines.append("Также в вопросе есть тема преимуществ при поступлении:")
            lines.append(
                "В моей базе есть общая информация о первоочередном и преимущественном праве, но конкретную категорию и документы нужно проверять по правилам приёма колледжа."
            )

        lines.append("")
        lines.append("Могу отдельно подробнее рассказать про поступление, документы или специальности.")
        return "\n".join(lines)

    def render_primary_multi_intent_block(self, db: Session, *, college: str | None, has_pedagogy: bool) -> list[str]:
        lines: list[str] = []
        if college:
            card = self.chat_service.get_college_card_for_name(db, college)
            display_name = self.chat_service.extract_college_name(card) if card else college
            lines.append(display_name)
            brief = self.brief_from_doc(card) if card else ""
            if brief and "Алиасы:" not in brief and "Адреса:" not in brief:
                lines.append(f"Кратко: {brief}")

            if has_pedagogy:
                specialty_docs = self.chat_service.get_all_specialty_docs_for_college(db, college)
                education_docs = [
                    doc
                    for doc in specialty_docs
                    if self.education_priority(normalize_label(self.chat_service.extract_specialty_name(doc))) is not None
                    and not any(marker in normalize_label(self.chat_service.extract_specialty_name(doc)) for marker in EDUCATION_EXCLUDE_WITHOUT_CONTEXT)
                ]
                if education_docs:
                    lines.append("Педагогические специальности в базе:")
                    for idx, doc in enumerate(education_docs[:3], start=1):
                        lines.append(f"{idx}. {self.chat_service.extract_specialty_name(doc)}")
                else:
                    lines.append("По педагогическим специальностям в этом колледже лучше сверить актуальный список на сайте колледжа или в Атласе профессий.")
            return lines

        if has_pedagogy:
            _, items = self.industry_specialty_options(db, "education")
            lines.append("По педагогике в первую очередь стоит смотреть такие специальности:")
            for idx, item in enumerate(items[:3], start=1):
                lines.append(f"{idx}. {item.get('specialty', '')}")
            return lines

        lines.append("По этой части вопроса мне нужно чуть больше конкретики: колледж, специальность или направление.")
        return lines

    def show_specialties_for_profession(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        message: str,
        *,
        query: str | None = None,
    ) -> ScenarioAnswer:
        search_query = query or message
        items = self.find_specialty_options(db, search_query)
        if not items:
            if self.is_cyber_query(search_query):
                self.session_service.update_route_state(
                    db,
                    session,
                    {"current_route": "profession", "route_step": "awaiting_profession"},
                )
                return self.save_direct(
                    db,
                    session,
                    message,
                    self.cyber_clarification_answer(state),
                    "profession",
                    ["Защита информации", "Сети и администрирование", "Программирование", "Изменить запрос", MAIN_MENU_BUTTON],
                )
            if self.is_jewelry_query(search_query):
                answer = (
                    "В моей базе нет прямого варианта по этому ювелирному запросу. "
                    "Можно посмотреть близкие творческие и ремесленные направления: декоративно-прикладное искусство, реставрацию, дизайн или работу с материалами."
                )
                return self.save_direct(
                    db,
                    session,
                    message,
                    answer,
                    "profession",
                    ["Дизайн и творчество", "Изменить запрос", MAIN_MENU_BUTTON],
                )
            answer = (
                "Я не нашёл точные специальности по этой профессии в своей базе. "
                "Попробуйте написать проще: например, программист, дизайнер, фотограф, педагог."
            )
            return self.save_direct(db, session, message, answer, "profession", ["Изменить запрос", MAIN_MENU_BUTTON])

        self.session_service.update_route_state(
            db,
            session,
            {
                "current_route": "profession",
                "route_step": "profession_specialties",
                "last_profession": search_query,
                "last_results": {
                    "kind": "specialty_options",
                    "query": search_query,
                    "items": items,
                    "offset": 0,
                },
            },
        )
        title = "Для этой профессии могут подойти такие специальности:"
        if self.is_cyber_query(search_query):
            title = "Если речь про легальную кибербезопасность, можно смотреть такие направления:"
        elif self.is_jewelry_query(search_query):
            title = "По ювелирному направлению в базе есть такие варианты:"
        return self.render_specialty_options_page(db, session, message, title)

    def find_specialty_options(self, db: Session, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        if self.is_cyber_query(query):
            return self.find_specialty_options_by_markers(db, CYBER_SPECIALTY_MARKERS, limit=limit)
        if self.is_jewelry_query(query):
            return self.find_jewelry_specialty_options(db, limit=limit)

        for match in self.chat_service.get_reference_catalog().match_professions(query, limit=3):
            for raw in match.colleges:
                specialty = str(raw.get("specialty") or "").strip()
                if not specialty:
                    continue
                norm = normalize_label(specialty)
                if norm in seen:
                    continue
                seen.add(norm)
                professions = [str(value).strip() for value in (raw.get("professions") or []) if str(value).strip()]
                result.append(
                    {
                        "specialty": specialty,
                        "why": f"в базе связана с профессией «{match.display_name}»",
                        "professions": professions,
                    }
                )
                if len(result) >= limit:
                    return result

        for doc in self.chat_service.find_specialty_docs_by_query(db, query):
            specialty = self.chat_service.extract_specialty_name(doc)
            norm = normalize_label(specialty)
            if not specialty or norm in seen:
                continue
            seen.add(norm)
            professions = [str(value).strip() for value in (doc.metadata_json.get("professions") or []) if str(value).strip()]
            result.append(
                {
                    "specialty": specialty,
                    "why": self.specialty_why(specialty),
                    "professions": professions,
                }
            )
            if len(result) >= limit:
                break

        return result

    def find_jewelry_specialty_options(self, db: Session, *, limit: int) -> list[dict[str, Any]]:
        entries = self.jewelry_specialty_entries(db)
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in entries:
            specialty = str(entry.get("specialty") or "").strip()
            if not specialty:
                continue
            norm = normalize_label(specialty)
            if norm in seen:
                continue
            seen.add(norm)
            result.append(
                {
                    "specialty": specialty,
                    "why": self.specialty_why(specialty),
                    "professions": [str(value).strip() for value in (entry.get("professions") or []) if str(value).strip()],
                }
            )
            if len(result) >= limit:
                break
        return result

    def find_specialty_options_by_markers(self, db: Session, markers: tuple[str, ...], *, limit: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        docs = db.scalars(select(Document).where(Document.doc_type == "specialty")).all()

        for doc in docs:
            specialty = self.chat_service.extract_specialty_name(doc)
            norm = normalize_label(specialty)
            if not norm or not any(marker in norm for marker in markers):
                continue
            if norm in seen:
                continue
            seen.add(norm)
            result.append(
                {
                    "specialty": specialty,
                    "why": self.specialty_why(specialty),
                    "professions": [str(value).strip() for value in (doc.metadata_json.get("professions") or []) if str(value).strip()],
                }
            )
            if len(result) >= limit:
                break

        return result

    def render_specialty_options_page(self, db: Session, session, user_message: str, title: str) -> ScenarioAnswer:
        state = self.session_service.get_route_state(session)
        last_results = state.get("last_results") if isinstance(state.get("last_results"), dict) else {}
        items = last_results.get("items", [])
        offset = int(last_results.get("offset") or 0)
        page = [item for item in items[offset : offset + 3] if isinstance(item, dict)]
        if not page:
            return self.save_direct(
                db,
                session,
                user_message,
                "Больше подходящих специальностей в моей базе не нашёл. Можно изменить запрос или выбрать другую отрасль.",
                "profession",
                ["Изменить запрос", "Выбрать другую отрасль", MAIN_MENU_BUTTON],
            )

        lines = [title]
        for idx, item in enumerate(page, start=offset + 1):
            lines.append("")
            lines.append(f"{idx}. Специальность: {item.get('specialty', '')}")
            lines.append(f"   Почему подходит: {item.get('why') or 'связана с выбранным направлением'}.")
            professions = item.get("professions") or []
            if professions:
                lines.append(f"   После обучения: {', '.join(str(p) for p in professions[:3])}")

        new_offset = offset + len(page)
        last_results = dict(last_results)
        last_results["offset"] = new_offset
        self.session_service.update_route_state(db, session, {"last_results": last_results})

        suggestions = [f"{idx}. Подробнее" for idx in range(offset + 1, offset + len(page) + 1)]
        if new_offset < len(items):
            suggestions.append("Показать ещё специальности")
        suggestions.extend(["Изменить запрос", "Выбрать другую отрасль", MAIN_MENU_BUTTON])
        return self.save_direct(db, session, user_message, "\n".join(lines), "profession", suggestions)

    def render_more_specialties(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        last_results = state.get("last_results") if isinstance(state.get("last_results"), dict) else {}
        if last_results.get("kind") not in {"specialty_options", "industry_specialties"}:
            return self.save_direct(db, session, message, "Сначала нужно найти профессию или направление.", "profession", ["Я знаю профессию", MAIN_MENU_BUTTON])
        return self.render_specialty_options_page(db, session, message, "Показываю ещё подходящие специальности:")

    def handle_admission(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        message: str,
        action_code: str,
        *,
        top_k: int,
    ) -> ScenarioAnswer:
        step = state.get("route_step")
        if action_code == "admission_start":
            return self.admission_start(db, session, state, message)

        if action_code.startswith("admission_topic:"):
            topic = action_code.split(":", 1)[1]
            query = ADMISSION_QUERIES.get(topic, message)
            return self.answer_admission_question(db, session, state, message, query, top_k=top_k)

        if state.get("current_route") != "admission":
            if message:
                return self.answer_admission_question(db, session, state, message, message, top_k=top_k)
            return self.admission_start(db, session, state, message)

        if action_code == "admission_other":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "admission", "route_step": "awaiting_admission_question"},
            )
            return self.save_direct(db, session, message, "Напишите вопрос про поступление.", "admission", ["Главное меню"])

        if step == "awaiting_admission_question" or message:
            return self.answer_admission_question(db, session, state, message, message, top_k=top_k)

        return self.admission_start(db, session, state, message)

    def admission_start(self, db: Session, session, state: dict[str, Any], message: str) -> ScenarioAnswer:
        self.session_service.update_route_state(
            db,
            session,
            {"current_route": "admission", "route_step": "admission_topics"},
        )
        return self.save_direct(
            db,
            session,
            message,
            "Выберите тему про поступление:",
            "admission",
            ADMISSION_TOPIC_BUTTONS,
        )

    def answer_admission_question(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        original_message: str,
        query: str,
        *,
        top_k: int,
    ) -> ScenarioAnswer:
        topic = self.admission_topic_from_text(original_message) or self.admission_topic_from_text(query)
        if self.has_svo_priority_query(query):
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "admission", "route_step": "admission_answer"},
            )
            answer = self.append_related_admission_topics(self.render_svo_priority_answer(state), "svo_priority")
            return self.save_direct(
                db,
                session,
                original_message,
                answer,
                "admission",
                self.admission_suggestions("svo_priority"),
            )
        if self.has_olympiad_benefit_query(query):
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "admission", "route_step": "admission_answer"},
            )
            answer = self.append_related_admission_topics(self.render_olympiad_benefit_answer(state), topic or "svo_priority")
            return self.save_direct(
                db,
                session,
                original_message,
                answer,
                "admission",
                self.admission_suggestions(topic or "svo_priority"),
            )
        if self.has_general_exam_query(query):
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "admission", "route_step": "admission_answer"},
            )
            answer = self.append_related_admission_topics(self.render_general_exams_answer(state), "exams")
            return self.save_direct(
                db,
                session,
                original_message,
                answer,
                "admission",
                ["Выбрать колледж", "Выбрать специальность", "Какие документы нужны", "Как подать заявление", MAIN_MENU_BUTTON],
            )
        answer = self.call_chat_service(
            db,
            session,
            state,
            query,
            original_message=original_message,
            route_updates={"current_route": "admission", "route_step": "admission_answer"},
            suggestions=self.admission_suggestions(topic),
            top_k=top_k,
            force_mode="admission",
        )
        answer.answer = self.append_related_admission_topics(answer.answer, topic)
        self.session_service.update_route_state(db, session, {"last_answer": answer.answer})
        return answer

    def handle_custom(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        message: str,
        action_code: str,
        *,
        top_k: int,
    ) -> ScenarioAnswer:
        if action_code == "custom_start" or state.get("current_route") != "custom":
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "custom", "route_step": "awaiting_custom_question"},
            )
            return self.save_direct(
                db,
                session,
                message,
                "Напишите свой вопрос о колледжах, специальностях или поступлении.",
                "custom",
                ["Главное меню"],
            )

        return self.route_free_message(db, session, state, message, top_k=top_k)

    def route_free_message(self, db: Session, session, state: dict[str, Any], message: str, *, top_k: int) -> ScenarioAnswer:
        if not message:
            return self.save_direct(db, session, message, self.main_menu_text(state), "main_menu", MAIN_MENU)

        college = self.chat_service.canonical_college_from_db(db, message) or self.chat_service.canonical_college_from_text(message)
        multi_intent_answer = self.render_multi_intent_answer(db, state, message, college=college)
        if multi_intent_answer:
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "custom", "route_step": "multi_intent"},
            )
            return self.save_direct(
                db,
                session,
                message,
                multi_intent_answer,
                "multi_intent",
                ["Поступление", "Выбрать профессию", MAIN_MENU_BUTTON],
            )

        if self.has_svo_priority_query(message):
            self.session_service.update_route_state(db, session, {"current_route": "admission", "route_step": "admission_answer"})
            return self.save_direct(
                db,
                session,
                message,
                self.append_related_admission_topics(self.render_svo_priority_answer(state), "svo_priority"),
                "admission",
                self.admission_suggestions("svo_priority"),
            )

        if self.is_cyber_query(message):
            self.session_service.update_route_state(db, session, {"current_route": "profession", "route_step": "profession_specialties"})
            return self.show_specialties_for_profession(db, session, state, message)

        if self.chat_service.is_out_of_scope_query(message):
            self.session_service.update_route_state(db, session, {"current_route": "custom", "route_step": "out_of_scope"})
            answer = "Я помогаю только с колледжами Москвы, специальностями и поступлением. Лучше выберите один из разделов или задайте вопрос по этой теме."
            return self.save_direct(db, session, message, answer, "out_of_scope", MAIN_MENU)

        if college:
            if self.chat_service.is_contact_query(message):
                self.session_service.update_route_state(
                    db,
                    session,
                    {"current_route": "college", "route_step": "college_contacts", "last_college": college},
                )
                return self.college_contacts(db, session, self.session_service.get_route_state(session), message)
            if self.chat_service.is_all_specialties_request(message):
                self.session_service.update_route_state(
                    db,
                    session,
                    {"current_route": "college", "route_step": "college_specialties", "last_college": college},
                )
                return self.college_specialties(db, session, self.session_service.get_route_state(session), message)
            self.session_service.update_route_state(
                db,
                session,
                {"current_route": "college", "route_step": "college_found", "last_college": college},
            )
            return self.search_college(db, session, self.session_service.get_route_state(session), message)

        if self.chat_service.is_faq_query(message):
            return self.answer_admission_question(db, session, state, message, message, top_k=top_k)

        if self.chat_service.is_catalog_recommendation_query(message) or self.chat_service.is_industry_professions_query(message):
            return self.call_chat_service(
                db,
                session,
                state,
                message,
                original_message=message,
                route_updates={"current_route": "profession", "route_step": "profession_answer"},
                suggestions=["Выбрать профессию", "Помочь выбрать колледж", "Главное меню"],
                top_k=top_k,
                force_mode="profession",
            )

        if self.chat_service.dialog_router.route(message).mode == "career_guidance":
            return self.call_chat_service(
                db,
                session,
                state,
                message,
                original_message=message,
                route_updates={"current_route": "profession", "route_step": "career_guidance"},
                suggestions=["Выбрать отрасль", "Я знаю профессию", "Главное меню"],
                top_k=top_k,
                force_mode="profession",
            )

        self.session_service.update_route_state(db, session, {"current_route": "custom", "route_step": "clarify"})
        answer = (
            "Я могу помочь, если вопрос про колледжи Москвы, специальности или поступление.\n\n"
            "Выберите раздел или переформулируйте вопрос ближе к этой теме."
        )
        return self.save_direct(db, session, message, answer, "custom", MAIN_MENU)

    def call_chat_service(
        self,
        db: Session,
        session,
        state: dict[str, Any],
        query: str,
        *,
        original_message: str,
        route_updates: dict[str, Any],
        suggestions: list[str],
        top_k: int,
        force_mode: str | None = None,
    ) -> ScenarioAnswer:
        self.session_service.update_route_state(db, session, route_updates)
        result = self.chat_service.ask(
            db=db,
            user_id=session.user_id,
            user_query=query,
            session_id=session.session_id,
            top_k=top_k,
        )
        answer = self.prepare_answer(str(result["answer"]), self.session_service.get_route_state(session))
        self.session_service.update_route_state(db, session, {"last_answer": answer})
        mode = force_mode or str(result.get("dialog_mode", "scenario"))
        route_state = self.session_service.get_route_state(session)
        return ScenarioAnswer(
            session_id=str(result["session_id"]),
            answer=answer,
            dialog_mode=mode,
            route=route_state.get("current_route"),
            step=route_state.get("route_step"),
            suggestions=suggestions,
        )
