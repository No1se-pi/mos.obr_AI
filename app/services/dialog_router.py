from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.llm.ollama_client import OllamaClient
from app.logger import get_logger

logger = get_logger(__name__)


ROUTER_MODES = {
    "recommend_colleges",
    "faq",
    "chat",
    "script",
    "detail",
    "detail_more",
    "career_guidance",
    "out_of_scope",
}

COLLEGE_ALIASES: dict[str, str] = {
    "каит 20": "Колледж автоматизации и информационных технологий № 20",
    "кaит 20": "Колледж автоматизации и информационных технологий № 20",
    "ит.москва": "ИТ.Москва",
    "ит москва": "ИТ.Москва",
    "кс 54": "Колледж связи № 54 имени П.М. Вострухина",
    "26 кадр": "Колледж Архитектуры, Дизайна и Реинжиниринга № 26",
    "мгпу": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    "испо ушинского": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    "ушинского": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
    # ВАЖНО: по договорённости проекта МПК = Московский педагогический колледж.
    # ММПК можно выбирать только при явном "музыкальный / музыкально-педагогический".
    "мпк": "Московский педагогический колледж",
    "московский педагогический колледж": "Московский педагогический колледж",
    "ммпк": "Московский музыкально-педагогический колледж",
    "музыкально-педагогический": "Московский музыкально-педагогический колледж",
    "колледж полиции": "Колледж полиции",
    "колледж добрых дел": "Московский колледж социальных профессий имени Е.И. Холостовой",
    "кдд": "Московский колледж социальных профессий имени Е.И. Холостовой",
    "финансовый колледж 35": "Финансовый колледж № 35",
    "колледж красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "техникум красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "красина": "Московский техникум креативных индустрий им. Л.Б. Красина",
    "мгпи": "МГПУ Институт среднего профессионального образования имени К. Д. Ушинского",
}

FAQ_TERMS = {
    "документы",
    "документ",
    "поступление",
    "поступить",
    "заявление",
    "сроки",
    "зачисление",
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
    "егэ",
    "огэ",
    "гвэ",
    "гия",
    "общежитие",
    "стипендия",
    "питание",
    "проезд",
    "практика",
    "трудоустройство",
    "целевое",
    "вступительные",
    "испытания",
    "экзамены",
    "mos.ru",
    "мос.ру",
    "сдавать",
    "особые условия",
    "специальные условия",
    "не могу сдавать",
}

CAREER_TERMS = {
    "хочу стать",
    "кем стать",
    "кем я хочу быть",
    "не знаю кем",
    "не знаю что хочу",
    "что делать",
    "профориентация",
    "интересно",
    "нравится",
    "люблю",
    "куда поступать",
    "на кого поступать",
    "что выбрать",
}

RECOMMEND_TERMS = {
    "посоветуй",
    "куда",
    "где учиться",
    "где учат",
    "где обуч",
    "учат на",
    "обучиться на",
    "какие колледжи",
    "какие есть колледжи",
    "какие колледжи готовят",
    "какие колледжи к этому готовят",
    "какие колледжи к этому",
    "колледжи есть",
    "подбери колледж",
    "подбери колледжи",
    "на кого",
    "логистика",
    "актер",
    "актёр",
    "дизайнер",
    "юрист",
    "полиция",
    "полицейский",
    "программист",
    "ml",
    "фотограф",
    "повар",
    "сварщик",
    "ювелир",
    "педагог",
    "учитель",
}

FAQ_ADMIN_TERMS = {
    "документ",
    "заявление",
    "срок",
    "зачисление",
    "льгот",
    "овз",
    "инвалид",
    "отсроч",
    "отстроч",
    "арм",
    "призыв",
    "военком",
    "общежит",
    "стипенд",
    "питание",
    "проезд",
    "практика",
    "целевое",
    "вступитель",
    "испытан",
    "экзам",
    "mos.ru",
    "мос.ру",
    "сдавать",
    "особые условия",
    "специальные условия",
    "правила поступ",
}

DOMAIN_RECOMMEND_TERMS = {
    "it",
    "айти",
    "программирование",
    "разработка",
    "информационная безопасность",
    "кибербезопасность",
    "медицина",
    "медицин",
    "дизайн",
    "логистика",
    "туризм",
    "финансы",
    "экономика",
    "строительство",
    "промышленность",
    "здравоохранение",
    "креативная индустрия",
    "архитектура",
    "медиа",
}

DETAIL_TERMS = {
    "расскажи про",
    "расскажи о",
    "расскажи об",
    "что за",
    "подробнее про",
    "инфа про",
    "расскажи подробнее про",
}

MORE_TERMS = {
    "еще инфы",
    "ещё инфы",
    "больше инфы",
    "подробнее",
    "больше",
    "расскажи подробнее",
    "расскажи про все",
    "все специальности",
    "остальные специальности",
    "какие еще специальности",
    "какие ещё специальности",
    "какие специальности есть",
}

SCRIPT_PATTERNS: dict[str, tuple[str, ...]] = {
    "greeting": ("привет", "здравствуйте", "здравствуй", "ку", "hello", "hi"),
    "intro": ("кто ты", "что ты можешь", "что ты умеешь", "как тебя зовут", "а что ты можешь"),
    "creator": ("создател", "кто тебя сделал", "кто тебя создал"),
    "attention": ("алее", "алё", "ау", "эй", "ха ха", "ахах"),
    "rating": ("оцени колледжи", "по десятибалльной", "10-балльной"),
    "favorite": ("любимый колледж", "любимый мем"),
    "source": ("откуда ты это знаешь", "откуда знаешь", "где ты это взял", "источник", "откуда твоя база", "откуда база", "база данных ответов", "откуда информация", "откуда инфа"),
}

ABUSE_TERMS = {
    "пидор", "нахуй", "хуй", "уеб", "уёб", "ебан", "еблан", "тупой", "дурак", "дура", "говно",
    "беспонтовый", "позорный", "чмо", "уебищ", "долбоеб", "долбоёб",
}

OUT_OF_SCOPE_TERMS = {
    "теорема", "теорему", "лагранжа", "рецепт", "вкусного кофе", "шутку", "мем",
    "напиши алгоритм", "бинарного поиска", "напиши код", "реши задачу", "домашку",
    "стриптиз", "стриптизер",
}

SAFETY_DIRECT_HARM_TERMS = {
    "как взломать",
    "помоги взломать",
    "взломай",
    "украсть пароль",
    "своровать пароль",
    "обойти защиту",
    "обойти пароль",
    "сделать вирус",
    "написать вирус",
    "вредоносный код",
    "ddos",
    "ддос",
    "фишинговый сайт",
    "фишинговую страницу",
    "подделать документы",
    "купить диплом",
    "сделать поддельный диплом",
    "поджечь",
    "рецепт бомбы",
    "рецепт взрывчат",
    "сделать бомбу",
    "собрать бомбу",
    "сделать помбу",
    "помбу",
    "взрывчатые вещества",
    "взрывчатку",
    "купить наркотики",
    "продать наркотики",
}

SAFETY_DANGEROUS_TOPICS = {
    "взлом",
    "пароль",
    "фишинг",
    "вирус",
    "троян",
    "кейлоггер",
    "ботнет",
    "ddos",
    "ддос",
    "эксплойт",
    "уязвимость",
    "оружие",
    "бомба",
    "помба",
    "помбу",
    "взрывчат",
    "наркотик",
    "поддельный документ",
}

SAFETY_INSTRUCTION_INTENTS = {
    "как сделать",
    "как написать",
    "как создать",
    "инструкция",
    "пошагово",
    "дай",
    "где учат",
    "учат делать",
    "научиться делать",
    "рецепт",
    "изготовить",
    "собрать",
    "научи",
    "скрипт",
    "код для",
    "команды для",
    "схема",
    "способ",
}

SAFE_CYBER_CAREER_TERMS = {
    "кибербезопасность",
    "информационная безопасность",
    "белый хакер",
    "этичный хакер",
    "пентестер",
    "специалист по информационной безопасности",
}


@dataclass(slots=True)
class RouterDecision:
    mode: str
    normalized_query: str
    topic: str | None = None
    college: str | None = None
    specialty: str | None = None
    script_type: str | None = None
    needs_retrieval: bool = True
    use_history: bool = False
    confidence: float = 0.5
    reason: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], fallback_query: str) -> "RouterDecision":
        mode = str(raw.get("mode") or "chat").strip()
        if mode not in ROUTER_MODES:
            mode = "chat"

        normalized_query = str(raw.get("normalized_query") or fallback_query).strip()
        if not normalized_query:
            normalized_query = fallback_query

        confidence_raw = raw.get("confidence", 0.5)
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = 0.5

        return cls(
            mode=mode,
            normalized_query=normalized_query,
            topic=_clean_optional(raw.get("topic")),
            college=_clean_optional(raw.get("college")),
            specialty=_clean_optional(raw.get("specialty")),
            script_type=_clean_optional(raw.get("script_type")),
            needs_retrieval=bool(raw.get("needs_retrieval", mode not in {"script", "chat", "out_of_scope", "career_guidance"})),
            use_history=bool(raw.get("use_history", False)),
            confidence=max(0.0, min(confidence, 1.0)),
            reason=str(raw.get("reason") or "").strip(),
        )


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s№.-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class DialogRouter:
    def __init__(self, llm_client: OllamaClient | None = None) -> None:
        self.llm_client = llm_client or OllamaClient()

    def route(self, user_query: str, history_messages: list | None = None) -> RouterDecision:
        q = normalize_text(user_query)
        history_messages = history_messages or []

        hard = self._hard_route(user_query, history_messages)
        if hard is not None:
            return hard

        quick = self._route_with_llm(user_query, history_messages, detailed=False)
        if quick.confidence >= 0.72 and quick.mode != "chat":
            return self._postprocess_decision(quick, user_query, history_messages)

        # Второй, более развёрнутый запрос только для неоднозначных случаев.
        detailed = self._route_with_llm(user_query, history_messages, detailed=True)
        if detailed.confidence >= quick.confidence:
            return self._postprocess_decision(detailed, user_query, history_messages)

        return self._postprocess_decision(quick, user_query, history_messages)


    def _last_assistant_looks_career_guidance(self, history_messages: list) -> bool:
        text = self._history_text(history_messages).lower()
        markers = [
            "тебе ближе", "какие у тебя есть хобби", "любимые школьные предметы",
            "помогу определиться", "профориента", "люди/педагогика", "творчество/дизайн",
            "какие предметы", "после этого я предложу", "ответь коротко",
            "я бы смотрел", "подходящие направления", "следующий шаг", "можно подобрать колледжи",
            "тебе больше нравится", "расскажи немного о себе", "работать с людьми",
        ]
        return any(marker in text for marker in markers)

    def _looks_like_career_guidance_answer(self, q: str) -> bool:
        if self._is_faq(q) or self.extract_college_alias(q):
            return False
        if any(term in q for term in OUT_OF_SCOPE_TERMS) or self._is_illegal_instruction(q):
            return False
        markers = [
            "матем", "информ", "физ", "литера", "общество", "история", "биология",
            "рисован", "творч", "люд", "дет", "помощ", "самостоят", "команд",
            "игр", "cs", "код", "айти", "it", "общаться", "нравится", "люблю",
            "предмет", "хобби", "легко", "не хочу", "хочу",
        ]
        return any(marker in q for marker in markers)

    def _hard_route(self, user_query: str, history_messages: list) -> RouterDecision | None:
        q = normalize_text(user_query)

        if self._is_gibberish(q):
            return RouterDecision(
                mode="script",
                normalized_query=user_query,
                script_type="nonsense",
                needs_retrieval=False,
                confidence=1.0,
                reason="gibberish",
            )

        if self._is_illegal_instruction(q):
            return RouterDecision(
                mode="script",
                normalized_query=user_query,
                script_type="safety",
                needs_retrieval=False,
                confidence=1.0,
                reason="safety_illegal_instruction",
            )

        if any(term in q for term in ABUSE_TERMS):
            return RouterDecision(
                mode="script",
                normalized_query=user_query,
                script_type="abuse",
                needs_retrieval=False,
                confidence=1.0,
                reason="abuse",
            )

        for script_type, patterns in SCRIPT_PATTERNS.items():
            if any(pattern in q for pattern in patterns):
                # "Привет, расскажи про КАИТ 20" не должен превращаться в обычное приветствие.
                if script_type == "greeting" and len(q.split()) > 2:
                    break
                return RouterDecision(
                    mode="script",
                    normalized_query=user_query,
                    script_type=script_type,
                    needs_retrieval=False,
                    confidence=1.0,
                    reason=f"script:{script_type}",
                )

        if any(term in q for term in OUT_OF_SCOPE_TERMS):
            return RouterDecision(
                mode="out_of_scope",
                normalized_query=user_query,
                needs_retrieval=False,
                confidence=0.98,
                reason="out_of_scope",
            )

        if self._last_assistant_looks_career_guidance(history_messages):
            if self._is_more_info(q):
                return RouterDecision(
                    mode="career_guidance",
                    normalized_query=user_query,
                    topic="профориентация",
                    needs_retrieval=False,
                    use_history=True,
                    confidence=0.94,
                    reason="career_guidance_more_followup",
                )

            if any(term in q for term in ["колледж", "колледжи", "куда", "где учиться", "что посмотреть"]):
                last_user = self._last_user_text(history_messages)
                normalized = f"{last_user}. {user_query}" if last_user else user_query
                return RouterDecision(
                    mode="recommend_colleges",
                    normalized_query=normalized,
                    topic="профориентация: подбор колледжей по прошлой теме",
                    needs_retrieval=True,
                    use_history=True,
                    confidence=0.92,
                    reason="career_guidance_to_recommendation",
                )

        # Если пользователь отвечает на профориентационные вопросы, не даём роутеру уронить это в FAQ/случайный retriever.
        if self._last_assistant_looks_career_guidance(history_messages) and self._looks_like_career_guidance_answer(q):
            return RouterDecision(
                mode="career_guidance",
                normalized_query=user_query,
                topic="профориентация",
                needs_retrieval=False,
                use_history=True,
                confidence=0.95,
                reason="career_guidance_followup",
            )

        college = self.extract_college_alias(user_query)
        if college:
            if self._is_more_info(q):
                return RouterDecision(
                    mode="detail_more",
                    normalized_query=f"{college}. Расскажи подробнее и покажи больше специальностей.",
                    college=college,
                    topic=college,
                    needs_retrieval=True,
                    confidence=0.98,
                    reason="college_more",
                )

            return RouterDecision(
                mode="detail",
                normalized_query=college,
                college=college,
                topic=college,
                needs_retrieval=True,
                confidence=0.96,
                reason="explicit_college",
            )

        # Administrative FAQ has priority over the broad "tell me about..." detail rule.
        # Otherwise requests like "tell me about army deferral" are mistaken for specialty details.
        if self._is_faq(q):
            return RouterDecision(
                mode="faq",
                normalized_query=self._normalize_faq_query(q, user_query),
                topic="faq",
                needs_retrieval=True,
                confidence=0.94,
                reason="faq_terms_before_detail",
            )

        if any(term in q for term in DETAIL_TERMS):
            return RouterDecision(
                mode="detail",
                normalized_query=user_query,
                topic=user_query,
                needs_retrieval=True,
                confidence=0.86,
                reason="detail_terms",
            )

        if self._is_more_info(q):
            last_college = self.extract_college_alias(self._history_text(history_messages))
            if last_college:
                return RouterDecision(
                    mode="detail_more",
                    normalized_query=f"{last_college}. Расскажи подробнее и покажи больше специальностей.",
                    college=last_college,
                    topic=last_college,
                    needs_retrieval=True,
                    use_history=True,
                    confidence=0.92,
                    reason="followup_more_college",
                )
            return RouterDecision(
                mode="chat",
                normalized_query=user_query,
                needs_retrieval=False,
                use_history=True,
                confidence=0.70,
                reason="followup_more_no_topic",
            )

        if self._is_ovz_help_interest(q):
            return RouterDecision(
                mode="career_guidance",
                normalized_query=user_query,
                topic="профориентация: помощь людям с ОВЗ и детям",
                needs_retrieval=False,
                use_history=True,
                confidence=0.96,
                reason="ovz_help_interest_not_faq",
            )

        if self._is_faq(q):
            return RouterDecision(
                mode="faq",
                normalized_query=self._normalize_faq_query(q, user_query),
                topic="faq",
                needs_retrieval=True,
                confidence=0.94,
                reason="faq_terms",
            )

        if self._is_recommend(q):
            return RouterDecision(
                mode="recommend_colleges",
                normalized_query=user_query,
                topic=user_query,
                needs_retrieval=True,
                confidence=0.86,
                reason="recommend_terms",
            )

        if self._is_career_guidance(q):
            return RouterDecision(
                mode="career_guidance",
                normalized_query=user_query,
                topic="профориентация",
                needs_retrieval=False,
                use_history=True,
                confidence=0.90,
                reason="career_guidance",
            )

        if self._looks_like_short_reaction(q):
            return RouterDecision(
                mode="chat",
                normalized_query=user_query,
                needs_retrieval=False,
                use_history=True,
                confidence=0.78,
                reason="short_reaction",
            )

        return None

    def _route_with_llm(self, user_query: str, history_messages: list, *, detailed: bool) -> RouterDecision:
        history = self._compact_history(history_messages, limit=8 if detailed else 4)

        if detailed:
            system_prompt = (
                "Ты маршрутизатор диалога для бота по колледжам Москвы. "
                "Твоя задача — выбрать режим, а не отвечать пользователю. "
                "Верни только JSON без markdown. "
                "Режимы: script, recommend_colleges, faq, chat, detail, detail_more, career_guidance, out_of_scope. "
                "script — приветствие, кто ты, как зовут, оскорбления, внимание, создатель. "
                "recommend_colleges — пользователь просит подобрать колледжи/специальности по профессии или направлению. "
                "faq — вопросы по правилам поступления, документам, армии, ОВЗ, питанию, общежитию, ЕГЭ/ОГЭ, mos.ru. "
                "chat — короткая болталка, реакция, непонятная реплика без запроса. "
                "detail — рассказать про конкретный колледж. "
                "detail_more — продолжение: больше информации, ещё специальности, подробнее про прошлый колледж. "
                "career_guidance — пользователь не знает, кем быть, просит помочь выбрать направление. "
                "out_of_scope — рецепты, теоремы, код, шутки, мемы, секс/стриптиз, запросы не про колледжи. "
                "Особое правило: МПК = Московский педагогический колледж. ММПК выбирай только при явном слове музыкальный."
            )
        else:
            system_prompt = (
                "Выбери режим для сообщения пользователя. Только JSON. "
                "modes: script,recommend_colleges,faq,chat,detail,detail_more,career_guidance,out_of_scope. "
                "МПК=Московский педагогический колледж. Армия/отсрочка/ОВЗ/документы=faq."
            )

        user_prompt = (
            "История диалога:\n"
            f"{history}\n\n"
            "Сообщение пользователя:\n"
            f"{user_query}\n\n"
            "Верни JSON строго такого вида:\n"
            '{"mode":"faq","normalized_query":"...","topic":null,"college":null,'
            '"specialty":null,"script_type":null,"needs_retrieval":true,'
            '"use_history":false,"confidence":0.9,"reason":"..."}'
        )

        try:
            raw = self.llm_client.generate(f"{system_prompt}\n\n{user_prompt}").strip()
            data = self._parse_json(raw)
            return RouterDecision.from_dict(data, fallback_query=user_query)
        except Exception as e:
            logger.warning(f"DialogRouter LLM route failed: {e}")
            return self._fallback_route(user_query, history_messages)

    def _fallback_route(self, user_query: str, history_messages: list) -> RouterDecision:
        hard = self._hard_route(user_query, history_messages)
        if hard is not None:
            return hard

        return RouterDecision(
            mode="chat",
            normalized_query=user_query,
            needs_retrieval=False,
            confidence=0.45,
            reason="fallback_chat",
        )

    def _postprocess_decision(
        self,
        decision: RouterDecision,
        user_query: str,
        history_messages: list,
    ) -> RouterDecision:
        q = normalize_text(user_query)

        # Не доверяем LLM в критичных кейсах.
        if self._is_illegal_instruction(q):
            return RouterDecision("script", user_query, script_type="safety", needs_retrieval=False, confidence=1.0)

        if any(term in q for term in ABUSE_TERMS):
            return RouterDecision("script", user_query, script_type="abuse", needs_retrieval=False, confidence=1.0)

        if any(term in q for term in OUT_OF_SCOPE_TERMS):
            return RouterDecision("out_of_scope", user_query, needs_retrieval=False, confidence=1.0)

        if self._is_ovz_help_interest(q):
            decision.mode = "career_guidance"
            decision.needs_retrieval = False
            decision.use_history = True
            decision.topic = "профориентация: помощь людям с ОВЗ и детям"
        elif self._is_faq(q):
            decision.mode = "faq"
            decision.needs_retrieval = True
            decision.normalized_query = self._normalize_faq_query(q, user_query)

        college = self.extract_college_alias(user_query)
        if college:
            decision.college = college
            decision.topic = college
            decision.needs_retrieval = True
            decision.normalized_query = college if decision.mode != "detail_more" else f"{college}. Больше информации и специальностей."
            if decision.mode not in {"detail", "detail_more"}:
                decision.mode = "detail"

        if decision.mode not in ROUTER_MODES:
            decision.mode = "chat"

        if decision.mode in {"script", "chat", "career_guidance", "out_of_scope"}:
            decision.needs_retrieval = False

        return decision

    def extract_college_alias(self, text: str) -> str | None:
        q = normalize_text(text)

        # "мпк" — точный отдельный токен, чтобы не ловить ММПК.
        if re.search(r"(^|\s)мпк($|\s)", q):
            return "Московский педагогический колледж"

        if "ммпк" in q or "музыкально педагогический" in q or "музыкально-педагогический" in q:
            return "Московский музыкально-педагогический колледж"

        for alias, canonical in COLLEGE_ALIASES.items():
            if alias in {"мпк", "ммпк"}:
                continue
            if alias in q:
                return canonical
        return None

    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON object in router response: {raw[:200]}")

        return json.loads(raw[start : end + 1])

    def _compact_history(self, history_messages: list, limit: int = 6) -> str:
        if not history_messages:
            return "Истории нет."

        chunks: list[str] = []
        for msg in history_messages[-limit:]:
            role = getattr(msg, "role", "")
            content = str(getattr(msg, "content", "")).strip()
            if not content:
                continue
            content = re.sub(r"\s+", " ", content)
            chunks.append(f"{role}: {content[:500]}")

        return "\n".join(chunks) or "Истории нет."

    def _history_text(self, history_messages: list) -> str:
        return "\n".join(str(getattr(msg, "content", "")) for msg in history_messages[-8:])

    def _last_user_text(self, history_messages: list) -> str:
        for msg in reversed(history_messages):
            if getattr(msg, "role", "") == "user":
                return str(getattr(msg, "content", "")).strip()
        return ""

    def _is_safe_cyber_career_query(self, q: str) -> bool:
        if not any(term in q for term in SAFE_CYBER_CAREER_TERMS):
            return False
        return any(term in q for term in ["куда", "где учиться", "колледж", "специальность", "профессия", "стать"])

    def _is_illegal_instruction(self, q: str) -> bool:
        if any(term in q for term in SAFETY_DIRECT_HARM_TERMS):
            return True
        if self._is_safe_cyber_career_query(q):
            return False
        has_dangerous_topic = any(term in q for term in SAFETY_DANGEROUS_TOPICS)
        has_instruction_intent = any(term in q for term in SAFETY_INSTRUCTION_INTENTS)
        return has_dangerous_topic and has_instruction_intent

    def _is_ovz_help_interest(self, q: str) -> bool:
        """ОВЗ как интерес помогать людям — это профориентация, а не FAQ про условия поступления."""
        has_ovz = "овз" in q or "инвалид" in q or "инвалидн" in q
        has_help_interest = any(x in q for x in ["люблю помогать", "хочу помогать", "помогать людям", "работать с детьми", "работать с людьми", "помощ", "дет"])
        has_admission_question = any(x in q for x in ["поступ", "льгот", "услов", "вступ", "сдавать", "экзам", "документ", "заявлен"])
        return has_ovz and has_help_interest and not has_admission_question

    def _is_faq(self, q: str) -> bool:
        if self._is_ovz_help_interest(q):
            return False
        if any(term in q for term in FAQ_ADMIN_TERMS):
            return True
        if any(term in q for term in FAQ_TERMS):
            if self._is_recommend(q):
                return False
            return True
        if "могут ли забрать" in q and "арм" in q:
            return True
        if "забрать в армию" in q:
            return True
        if "вступитель" in q and ("не могу" in q or "как все" in q or "сдавать" in q):
            return True
        if "особые условия" in q or "специальные условия" in q:
            return True
        return False

    def _normalize_faq_query(self, q: str, original: str) -> str:
        if "арм" in q or "отсроч" in q or "отстроч" in q or "забрать" in q:
            return "отсрочка от армии при обучении в колледже"
        if "овз" in q or "инвалид" in q:
            return "особенности поступления для лиц с ОВЗ"
        return original

    def _is_career_guidance(self, q: str) -> bool:
        return any(term in q for term in CAREER_TERMS)

    def _is_recommend(self, q: str) -> bool:
        if any(term in q for term in RECOMMEND_TERMS):
            return True
        has_domain = any(term in q for term in DOMAIN_RECOMMEND_TERMS)
        has_intent = any(
            term in q
            for term in [
                "колледж",
                "колледжи",
                "учиться",
                "поступить",
                "поступать",
                "посовет",
                "подбери",
                "професс",
                "специальн",
            ]
        )
        return has_domain and has_intent

    def _is_more_info(self, q: str) -> bool:
        return any(term in q for term in MORE_TERMS)

    def _looks_like_short_reaction(self, q: str) -> bool:
        return len(q.split()) <= 4 and not self._is_faq(q) and not self._is_recommend(q)

    def _is_gibberish(self, q: str) -> bool:
        if len(q) < 12:
            return False

        words = re.findall(r"[а-яa-zё]+", q)
        if not words:
            return True

        # Длинные нормальные русские слова — не мусор.
        if any(re.search(r"[а-яё]{6,}", word) for word in words):
            return False

        repeated = any(len(set(word)) <= 2 and len(word) >= 12 for word in words)
        long_latin = any(re.search(r"[a-z]{14,}", word) for word in words)
        return repeated or long_latin
