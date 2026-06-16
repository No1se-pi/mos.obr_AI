import unittest
from dataclasses import dataclass

from app.db.repository import Document
from app.services.chat_service import ATLAS_URL, ChatService
from app.services.dialog_router import RouterDecision


@dataclass
class Message:
    role: str
    content: str


class FakeErrorLLM:
    def generate(self, prompt: str) -> str:
        return "Ошибка при обращении к модели"


class FakeHallucinatingLLM:
    def generate(self, prompt: str) -> str:
        return "Московский колледж экономики имени Ломоносова"


class FakeScalarResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class FakeDb:
    def __init__(self, documents):
        self.documents = documents

    def scalars(self, _stmt):
        return FakeScalarResult(self.documents)


class ChatServiceRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ChatService.__new__(ChatService)

    def test_detail_fallback_uses_soft_verification_language(self) -> None:
        answer = self.service.render_detail_fallback([])

        self.assertIn("могу ошибаться", answer)
        self.assertIn(ATLAS_URL, answer)
        self.assertNotIn("нет достаточных данных в базе", answer.lower())

    def test_unknown_institution_response_points_to_atlas(self) -> None:
        answer = self.service.render_unknown_institution_response()

        self.assertIn("могу ошибаться", answer)
        self.assertIn(ATLAS_URL, answer)

    def test_career_guidance_handles_no_code_followup(self) -> None:
        history = [
            Message(
                "assistant",
                "Если тебе нравятся математика, информатика и игры, это хороший вход в IT. "
                "Я бы смотрел разработку, сетевое администрирование и информационную безопасность.",
            )
        ]
        decision = RouterDecision(
            mode="career_guidance",
            normalized_query="Не хочу только сидеть в коде",
            needs_retrieval=False,
            use_history=True,
        )

        answer = self.service.render_career_guidance_answer(decision, history)

        self.assertIn("Сетевое", answer)
        self.assertIn("Информационная безопасность", answer)
        self.assertNotIn("о чём речь", answer.lower())

    def test_safety_script_has_safe_career_redirect(self) -> None:
        answer = self.service.pick_script_answer(
            RouterDecision(
                mode="script",
                normalized_query="как взломать сайт колледжа",
                script_type="safety",
                needs_retrieval=False,
            ),
            "как взломать сайт колледжа",
        )

        self.assertTrue("не" in answer.lower())
        self.assertTrue("безопас" in answer.lower() or "иб" in answer.lower())

    def test_ollama_error_text_is_rejected(self) -> None:
        self.assertEqual(self.service.clean_llm_output("Ошибка при обращении к модели"), "")

    def test_faq_fallback_is_used_when_llm_is_unavailable(self) -> None:
        self.service.llm_client = FakeErrorLLM()

        answer = self.service.try_llm_answer("faq", "Расскажи про отсрочку", [], [])

        self.assertNotIn("Ошибка при обращении к модели", answer)
        self.assertIn("могу ошибаться", answer.lower())

    def test_simplify_confirmation_reuses_previous_faq_answer(self) -> None:
        history = [
            Message(
                "assistant",
                "Подать заявление можно через mos.ru. Заявление должно получить статус «Принято».\n\n"
                "Если хочешь, могу объяснить это проще.",
            )
        ]

        self.assertTrue(self.service.should_simplify_previous_answer("давай", history))
        answer = self.service.render_simple_explanation(history)

        self.assertIn("Проще говоря", answer)
        self.assertIn("mos.ru", answer)
        self.assertNotIn("Графический дизайнер", answer)

    def test_short_ordinal_followup_reuses_numbered_career_list(self) -> None:
        history = [
            Message(
                "assistant",
                "Я бы смотрел так:\n"
                "1. Колледж А — Разработка программного обеспечения\n"
                "2. Колледж Б — Сетевое и системное администрирование\n"
                "3. Колледж В — Информационная безопасность\n\n"
                "Следующий шаг: могу подобрать колледжи по этим IT-направлениям.",
            )
        ]

        self.assertEqual(self.service.extract_ordinal_request("давай третье"), 3)
        self.assertEqual(self.service.extract_ordinal_request("3"), 3)
        self.assertIsNone(self.service.extract_ordinal_request("как поступить после 9"))

        college, specs = self.service.parse_last_numbered_specialties(history)

        self.assertIsNone(college)
        self.assertEqual(specs[2], "Информационная безопасность")

    def test_ordinal_followup_ignores_plain_faq_numbered_list(self) -> None:
        history = [
            Message(
                "assistant",
                "Для поступления обычно нужны:\n"
                "1. Паспорт\n"
                "2. Аттестат\n"
                "3. Заявление",
            )
        ]

        self.assertEqual(self.service.parse_last_numbered_specialties(history), (None, []))

    def test_recommendation_mode_does_not_use_hallucinating_llm(self) -> None:
        self.service.llm_client = FakeHallucinatingLLM()
        doc = Document(
            doc_type="specialty",
            title="ИБ",
            content="",
            metadata_json={
                "college_name": "ИТ.Москва",
                "specialty_name": "Обеспечение информационной безопасности автоматизированных систем",
                "professions": ["Специалист по информационной безопасности"],
            },
            embedding_json=[],
        )

        answer = self.service.try_llm_answer("recommend", "ИБ", [doc], [])

        self.assertIn("ИТ.Москва", answer)
        self.assertNotIn("Ломоносов", answer)

    def test_chat_mode_does_not_name_colleges_without_rag(self) -> None:
        self.service.llm_client = FakeHallucinatingLLM()
        answer = self.service.render_chat_answer(
            RouterDecision(mode="chat", normalized_query="давай", needs_retrieval=False),
            [],
        )

        self.assertNotIn("Ломоносов", answer)
        self.assertIn("чуть конкретнее", answer)

    def test_more_colleges_request_skips_previous_colleges(self) -> None:
        docs = [
            Document(
                doc_type="specialty",
                title="old",
                content="",
                metadata_json={
                    "college_name": "Колледж автоматизации и информационных технологий № 20",
                    "specialty_name": "Графический дизайнер",
                    "professions": ["Графический дизайнер"],
                },
                embedding_json=[],
            ),
            Document(
                doc_type="specialty",
                title="new",
                content="",
                metadata_json={
                    "college_name": "Технологический колледж № 21",
                    "specialty_name": "Графический дизайнер",
                    "professions": ["Графический дизайнер"],
                },
                embedding_json=[],
            ),
        ]

        answer = self.service.render_recommendation_fallback(
            docs,
            "Какие ещё колледжи есть?",
            skip_colleges={self.service.college_key("Колледж автоматизации и информационных технологий № 20")},
            is_more_request=True,
        )

        self.assertIn("Технологический колледж № 21", answer)
        self.assertNotIn("Колледж автоматизации и информационных технологий № 20", answer)

    def test_contact_query_renders_contacts_without_general_overview(self) -> None:
        doc = Document(
            doc_type="college",
            title="КАИТ 20",
            content="",
            metadata_json={
                "college_name": "Колледж автоматизации и информационных технологий № 20",
                "contacts": ["8 (499) 164-49-30", "priem@kait20.ru", "https://vk.com/kait_20_official"],
                "website": "https://kait20.mskobr.ru/",
                "addresses": ["САО, улица Расковой 4"],
            },
            embedding_json=[],
        )
        self.service.get_college_card_for_name = lambda db, name: doc

        answer = self.service.render_college_contacts(None, "КАИТ 20", "Дай контакты колледжа КАИТ 20")

        self.assertIn("https://kait20.mskobr.ru/", answer)
        self.assertIn("8 (499) 164-49-30", answer)
        self.assertIn("priem@kait20.ru", answer)
        self.assertNotIn("Что здесь можно изучать", answer)

    def test_address_query_renders_addresses_without_general_overview(self) -> None:
        doc = Document(
            doc_type="college",
            title="КАИТ 20",
            content="",
            metadata_json={
                "college_name": "Колледж автоматизации и информационных технологий № 20",
                "contacts": ["8 (499) 164-49-30", "priem@kait20.ru"],
                "website": "https://kait20.mskobr.ru/",
                "addresses": ["САО, улица Расковой 4"],
            },
            embedding_json=[],
        )
        self.service.get_college_card_for_name = lambda db, name: doc

        answer = self.service.render_college_contacts(None, "КАИТ 20", "По какому адресу находится КАИТ 20?")

        self.assertIn("Адреса:", answer)
        self.assertIn("САО, улица Расковой 4", answer)
        self.assertNotIn("8 (499) 164-49-30", answer)
        self.assertNotIn("Что здесь можно изучать", answer)

    def test_address_phrases_are_contact_queries(self) -> None:
        for query in [
            "какой адрес отделения?",
            "по какому адресу находится КАИТ 20?",
            "где расположен колледж Красина?",
            "как добраться до колледжа связи 54?",
        ]:
            with self.subTest(query=query):
                self.assertTrue(self.service.is_contact_query(query))

    def test_profession_catalog_recommends_known_colleges(self) -> None:
        answer = self.service.render_profession_recommendations_from_catalog(
            "Я хочу поступить на программиста, какие колледжи посоветуешь?"
        )

        self.assertIsNotNone(answer)
        self.assertIn("Программист", answer)
        self.assertIn("ИТ.Москва", answer)
        self.assertNotIn("Ломоносов", answer)

    def test_industry_catalog_lists_professions(self) -> None:
        answer = self.service.render_industry_professions_from_catalog("Какие профессии есть в отрасли IT?")

        self.assertIsNotNone(answer)
        self.assertIn("IT и цифровые технологии", answer)
        self.assertIn("Программист", answer)

    def test_specialty_detail_query_uses_database_specialty(self) -> None:
        docs = [
            Document(
                doc_type="specialty",
                title="МК1 — Сестринское дело",
                content="",
                metadata_json={
                    "college_name": "Медицинский колледж № 1",
                    "specialty_name": "Сестринское дело",
                    "professions": ["Медицинская сестра", "Медицинский брат"],
                    "website": "https://medcollege1.mskobr.ru/",
                },
                embedding_json=[],
            ),
            Document(
                doc_type="specialty",
                title="МК2 — Сестринское дело",
                content="",
                metadata_json={
                    "college_name": "Медицинский колледж № 2",
                    "specialty_name": "Сестринское дело",
                    "professions": ["Медицинская сестра"],
                    "website": "https://medcollege2.mskobr.ru/",
                },
                embedding_json=[],
            ),
        ]

        answer = self.service.render_specialty_detail_by_query(FakeDb(docs), "Расскажи про Сестринское дело")

        self.assertIsNotNone(answer)
        self.assertIn("Сестринское дело", answer)
        self.assertIn("Медицинский колледж № 1", answer)
        self.assertIn("Медицинский колледж № 2", answer)
        self.assertNotIn("Я на связи", answer)

    def test_cleanup_removes_markdown_angle_urls_and_truncated_links(self) -> None:
        text = "**Технологический колледж № 21**\n<https://example.mskobr.ru/>\nСайт: https://1-m..."

        cleaned = self.service.clean_llm_output(text)

        self.assertIn("Технологический колледж № 21", cleaned)
        self.assertIn("https://example.mskobr.ru/", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("<https://", cleaned)
        self.assertNotIn("https://1-m...", cleaned)

    def test_college_existence_followup_is_detected(self) -> None:
        self.assertTrue(self.service.is_college_existence_question("А такой колледж точно есть?"))
        self.assertTrue(self.service.is_college_existence_question("Он реально есть?"))
        self.assertFalse(self.service.is_college_existence_question("Какие колледжи есть?"))


if __name__ == "__main__":
    unittest.main()
