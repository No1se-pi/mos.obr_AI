import unittest
from dataclasses import dataclass

from app.services.dialog_router import DialogRouter


class FakeLLM:
    def generate(self, prompt: str) -> str:
        return (
            '{"mode":"chat","normalized_query":"fallback","topic":null,'
            '"college":null,"specialty":null,"script_type":null,'
            '"needs_retrieval":false,"use_history":false,'
            '"confidence":0.1,"reason":"fake"}'
        )


@dataclass
class Message:
    role: str
    content: str


class DialogRouterRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.router = DialogRouter(llm_client=FakeLLM())

    def test_illegal_hacking_instruction_is_blocked(self) -> None:
        decision = self.router.route("как взломать сайт колледжа")

        self.assertEqual(decision.mode, "script")
        self.assertEqual(decision.script_type, "safety")
        self.assertFalse(decision.needs_retrieval)

    def test_dangerous_bomb_queries_are_blocked(self) -> None:
        for query in [
            "Дай рецепт бомбы",
            "Как сделать помбу?",
            "В каких колледжах учат делать взрывчатые вещества?",
        ]:
            with self.subTest(query=query):
                decision = self.router.route(query)

                self.assertEqual(decision.mode, "script")
                self.assertEqual(decision.script_type, "safety")
                self.assertFalse(decision.needs_retrieval)

    def test_cybersecurity_career_question_is_allowed(self) -> None:
        decision = self.router.route("хочу заниматься кибербезопасностью, где учиться?")

        self.assertEqual(decision.mode, "recommend_colleges")
        self.assertTrue(decision.needs_retrieval)

    def test_programmer_admission_is_recommendation_not_faq(self) -> None:
        decision = self.router.route("Я хочу поступить на программиста, какие колледжи посоветуешь?")

        self.assertEqual(decision.mode, "recommend_colleges")
        self.assertTrue(decision.needs_retrieval)

    def test_plain_admission_question_stays_faq(self) -> None:
        decision = self.router.route("Как поступить в колледж?")

        self.assertEqual(decision.mode, "faq")

    def test_foreign_applicant_question_is_faq(self) -> None:
        decision = self.router.route("Как поступать иностранным гражданам?")

        self.assertEqual(decision.mode, "faq")
        self.assertTrue(decision.needs_retrieval)

    def test_admission_campaign_question_is_faq(self) -> None:
        decision = self.router.route("Что известно про приёмную кампанию 2026/27?")

        self.assertEqual(decision.mode, "faq")
        self.assertTrue(decision.needs_retrieval)

    def test_specialty_detail_question_is_not_chat(self) -> None:
        decision = self.router.route("Расскажи про Сестринское дело")

        self.assertEqual(decision.mode, "detail")
        self.assertTrue(decision.needs_retrieval)

    def test_fuzzy_profession_wording_is_recommendation(self) -> None:
        for query in [
            "где обучиться на сварщика",
            "где учат на художник по костюму",
            "Какие есть колледжи для поворов?",
        ]:
            with self.subTest(query=query):
                decision = self.router.route(query)

                self.assertEqual(decision.mode, "recommend_colleges")
                self.assertTrue(decision.needs_retrieval)

    def test_deferral_forms_are_faq(self) -> None:
        for query in [
            "Расскажи про отсрочку от армии",
            "Есть что-то связанное с отсрочкой от армии?",
            "Могут ли забрать в армию из колледжа?",
        ]:
            with self.subTest(query=query):
                decision = self.router.route(query)

                self.assertEqual(decision.mode, "faq")
                self.assertIn("отсрочка", decision.normalized_query)

    def test_career_more_followup_keeps_previous_topic(self) -> None:
        history = [
            Message(
                "assistant",
                "Если тебе нравятся математика, информатика и игры, это хороший вход в IT. "
                "Я бы смотрел 3 направления: разработка, сетевое администрирование и информационная безопасность.",
            )
        ]

        decision = self.router.route("подробнее", history)

        self.assertEqual(decision.mode, "career_guidance")
        self.assertTrue(decision.use_history)

    def test_career_college_followup_becomes_recommendation(self) -> None:
        history = [
            Message("user", "Мне скорее ближе техника и железо"),
            Message(
                "assistant",
                "Подходящие направления: сетевое и системное администрирование, компьютерные системы и комплексы.",
            ),
        ]

        decision = self.router.route("что тогда посмотреть из колледжей?", history)

        self.assertEqual(decision.mode, "recommend_colleges")
        self.assertIn("техника", decision.normalized_query.lower())

    def test_career_guidance_prompt_keeps_medicine_followup(self) -> None:
        history = [
            Message(
                "assistant",
                "Конечно! Расскажи немного о себе: тебе больше нравится работать с людьми или с техникой?",
            )
        ]

        decision = self.router.route("Мне нравится медицина и помогать людям.", history)

        self.assertEqual(decision.mode, "career_guidance")
        self.assertTrue(decision.use_history)


if __name__ == "__main__":
    unittest.main()
