import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.chat_models import ChatMessage, ChatSession
from app.db.repository import Base, Document
from app.services.scenario_service import ADMISSION_TOPIC_BUTTONS, ScenarioService
from app.services.session_service import SessionService


class FakeChatService:
    def __init__(self) -> None:
        self.session_service = SessionService()

    def canonical_college_from_db(self, db, text: str) -> str | None:
        return self.canonical_college_from_text(text)

    def canonical_college_from_text(self, text: str) -> str | None:
        return "Колледж автоматизации и информационных технологий № 20" if "КАИТ" in text.upper() else None

    def get_college_card_for_name(self, db, college_name: str):
        _ = college_name
        return db.query(Document).filter(Document.doc_type == "college").first()

    def extract_college_name(self, doc) -> str:
        return str(doc.metadata_json.get("college_name") or "")

    def extract_specialty_name(self, doc) -> str:
        return str(doc.metadata_json.get("specialty_name") or "")

    def college_key(self, name: str) -> str:
        return name.lower().strip()


class ScenarioServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ScenarioService.__new__(ScenarioService)

    def test_resolve_main_buttons(self) -> None:
        self.assertEqual(
            self.service.resolve_action(message="Выбрать колледж", route=None, action=None),
            "college_start",
        )
        self.assertEqual(
            self.service.resolve_action(message="Абитуриент / поступающий", route=None, action=None),
            "set_applicant",
        )
        self.assertEqual(
            self.service.resolve_action(message="Правила приёма в 2026 году", route=None, action=None),
            "admission_topic:rules_2026",
        )
        self.assertEqual(
            self.service.resolve_action(message="СВО и первоочередное право", route=None, action=None),
            "admission_topic:svo_priority",
        )
        self.assertEqual(
            self.service.resolve_action(message="1. Подробнее", route=None, action=None),
            "pick:1",
        )
        self.assertEqual(
            self.service.resolve_action(message="", route=None, action="industry:education"),
            "industry:education",
        )
        self.assertEqual(
            self.service.resolve_action(
                message="Педагогика и работа с детьми",
                route="profession",
                action="select_industry",
            ),
            "industry:education",
        )
        self.assertEqual(
            self.service.resolve_action(message="", route=None, action="details_2"),
            "pick:2",
        )

    def test_svo_topic_is_hidden_from_admission_buttons(self) -> None:
        self.assertNotIn("СВО и первоочередное право", ADMISSION_TOPIC_BUTTONS)

    def test_first_role_answer_is_natural(self) -> None:
        applicant = self.service.main_menu_text({"user_type": "applicant"}, first_time=True)
        parent = self.service.main_menu_text({"user_type": "parent"}, first_time=True)

        self.assertIn("Привет!", applicant)
        self.assertIn("следующую ступень", applicant)
        self.assertIn("Здравствуйте!", parent)
        self.assertIn("Выберите, с чего удобнее начать", parent)
        self.assertNotIn("Буду объяснять", applicant)
        self.assertNotIn("Буду обращаться", parent)

    def test_parent_tone_rewrites_common_phrases(self) -> None:
        text = "Если хочешь, напиши, что тебе интересно."
        result = self.service.apply_parent_tone(text)

        self.assertIn("хотите", result.lower())
        self.assertIn("напишите", result.lower())
        self.assertIn("вам", result.lower())

    def test_college_route_keeps_state(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        _ = ChatSession, ChatMessage
        db.add(
            Document(
                doc_type="college",
                title="КАИТ 20",
                content="Колледж автоматизации и информационных технологий № 20 готовит специалистов для IT.",
                metadata_json={
                    "college_name": "Колледж автоматизации и информационных технологий № 20",
                    "aliases": ["КАИТ 20"],
                },
                embedding_json=[],
            )
        )
        db.commit()

        service = ScenarioService(chat_service=FakeChatService())
        first = service.ask(db, "u1", "Абитуриент / поступающий")
        route = service.ask(db, "u1", "Выбрать колледж", session_id=first["session_id"])
        prompt = service.ask(db, "u1", "Найти конкретный колледж", session_id=first["session_id"])
        found = service.ask(db, "u1", "КАИТ 20", session_id=first["session_id"])

        self.assertEqual(route["route"], "college")
        self.assertEqual(prompt["step"], "awaiting_college_name")
        self.assertEqual(found["step"], "college_found")
        self.assertIn("Все специальности", found["suggestions"])

    def test_first_request_can_execute_route_action_with_user_type(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add(
            Document(
                doc_type="college",
                title="КАИТ 20",
                content="Колледж автоматизации и информационных технологий № 20 готовит специалистов для IT.",
                metadata_json={
                    "college_name": "Колледж автоматизации и информационных технологий № 20",
                    "aliases": ["КАИТ 20"],
                },
                embedding_json=[],
            )
        )
        db.commit()

        service = ScenarioService(chat_service=FakeChatService())
        result = service.ask(
            db,
            "u2",
            "КАИТ 20",
            route="college",
            action="search_college",
            user_type="applicant",
        )

        self.assertEqual(result["route"], "college")
        self.assertEqual(result["step"], "college_found")

    def test_education_industry_does_not_prioritize_vocal(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add_all(
            [
                Document(
                    doc_type="specialty",
                    title="Дошкольное образование",
                    content="",
                    metadata_json={
                        "college_name": "Московский педагогический колледж",
                        "specialty_name": "Дошкольное образование",
                        "professions": ["Воспитатель"],
                    },
                    embedding_json=[],
                ),
                Document(
                    doc_type="specialty",
                    title="Вокальное искусство",
                    content="",
                    metadata_json={
                        "college_name": "Музыкальный колледж",
                        "specialty_name": "Вокальное искусство",
                        "professions": ["Педагог по вокалу"],
                    },
                    embedding_json=[],
                ),
            ]
        )
        db.commit()

        service = ScenarioService(chat_service=FakeChatService())
        _, items = service.industry_specialty_options(db, "education")
        names = [item["specialty"] for item in items]

        self.assertIn("Дошкольное образование", names)
        self.assertNotIn("Вокальное искусство", names[:3])

    def test_cyber_query_returns_security_not_random_production(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add_all(
            [
                Document(
                    doc_type="specialty",
                    title="ИБ",
                    content="",
                    metadata_json={
                        "college_name": "ИТ.Москва",
                        "specialty_name": "Обеспечение информационной безопасности автоматизированных систем",
                        "professions": ["Специалист по информационной безопасности"],
                    },
                    embedding_json=[],
                ),
                Document(
                    doc_type="specialty",
                    title="Полимеры",
                    content="",
                    metadata_json={
                        "college_name": "Промышленный колледж",
                        "specialty_name": "Технология производства изделий из полимерных композитов",
                        "professions": ["Технолог"],
                    },
                    embedding_json=[],
                ),
            ]
        )
        db.commit()

        service = ScenarioService(chat_service=FakeChatService())
        items = service.find_specialty_options(db, "Ещё мне нравится хакинг")
        names = [item["specialty"] for item in items]

        self.assertIn("Обеспечение информационной безопасности автоматизированных систем", names)
        self.assertNotIn("Технология производства изделий из полимерных композитов", names)

    def test_interest_rules_prioritize_education_for_children(self) -> None:
        directions = self.service.infer_directions("Мне нравится работать с детьми и объяснять")

        self.assertEqual(directions[0][0], "education")

    def test_jewelry_interest_uses_relevant_specialties(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add_all(
            [
                Document(
                    doc_type="specialty",
                    title="Ювелир",
                    content="",
                    metadata_json={
                        "college_name": "Колледж декоративно-прикладного искусства имени Карла Фаберже",
                        "specialty_name": "Ювелир",
                        "professions": ["Ювелир-закрепщик", "Ювелир-монтировщик"],
                    },
                    embedding_json=[],
                ),
                Document(
                    doc_type="specialty",
                    title="Полимеры",
                    content="",
                    metadata_json={
                        "college_name": "Промышленный колледж",
                        "specialty_name": "Технология производства изделий из полимерных композитов",
                        "professions": ["Технолог"],
                    },
                    embedding_json=[],
                ),
            ]
        )
        db.commit()

        service = ScenarioService(chat_service=FakeChatService())
        items = service.find_specialty_options(db, "Мне нравится ювелирное дело и украшения")
        names = [item["specialty"] for item in items]

        self.assertIn("Ювелир", names)
        self.assertNotIn("Технология производства изделий из полимерных композитов", names)

    def test_general_exams_answer_is_not_ovz(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()

        service = ScenarioService(chat_service=FakeChatService())
        first = service.ask(db, "u3", "Абитуриент / поступающий")
        result = service.ask(
            db,
            "u3",
            "",
            session_id=first["session_id"],
            action="admission_topic:exams",
        )

        self.assertIn("нет полного списка вступительных испытаний", result["answer"])
        self.assertIn("Можно ещё посмотреть", result["answer"])
        self.assertNotIn("ОВЗ", result["answer"])
        self.assertIn("Выбрать колледж", result["suggestions"])

    def test_svo_answer_is_soft_and_has_related_topics(self) -> None:
        answer = self.service.append_related_admission_topics(
            self.service.render_svo_priority_answer({"user_type": "parent"}),
            "svo_priority",
        )

        self.assertIn("По одному сообщению нельзя точно подтвердить", answer)
        self.assertIn("приёмной комиссии", answer)
        self.assertIn("Можно ещё посмотреть", answer)
        self.assertNotIn("право точно положено", answer)


if __name__ == "__main__":
    unittest.main()
