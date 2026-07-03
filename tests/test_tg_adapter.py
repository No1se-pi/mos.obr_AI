import unittest

from app.interfaces.tg_adapter import TELEGRAM_SAFE_HTML_LIMIT, TelegramChatAdapter
from app.interfaces.telegram_bot import (
    TELEGRAM_CALLBACK_DATA_LIMIT,
    scenario_keyboard,
    telegram_button_label,
)


class TelegramAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = TelegramChatAdapter.__new__(TelegramChatAdapter)

    def test_long_answer_is_split_into_safe_html_chunks(self) -> None:
        long_answer = "Колледж с большим списком специальностей:\n" + "\n".join(
            f"{idx}. Специальность {idx} — после обучения: профессия {idx}, еще одна профессия {idx}"
            for idx in range(1, 180)
        )

        chunks = self.adapter.format_answer_chunks_html(long_answer)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= TELEGRAM_SAFE_HTML_LIMIT for chunk in chunks))

        for chunk in chunks:
            self.assertEqual(chunk.count("<b>"), chunk.count("</b>"))
            self.assertEqual(chunk.count("<code>"), chunk.count("</code>"))
            self.assertEqual(chunk.count("<blockquote>"), chunk.count("</blockquote>"))
            self.assertNotEqual(chunk.strip(), "")

    def test_telegram_button_icons_are_varied(self) -> None:
        labels = {
            "Хочу поступить": "🎓",
            "Хочу узнать информацию": "ℹ️",
            "Как подать заявление": "📨",
            "Какие документы нужны": "📄",
            "Сроки поступления": "📅",
            "Вступительные испытания": "🧪",
            "Бюджет и конкурс": "💰",
            "Льготы при поступлении": "🎖️",
            "Поступление иностранцев": "🌍",
            "Правила приёма 2026/27": "📜",
            "Промышленность": "🏭",
            "ИТ": "💻",
            "Креативные индустрии": "🎨",
            "Образование и социальная сфера": "🎒",
            "Главное меню": "🏠",
        }

        for label, icon in labels.items():
            with self.subTest(label=label):
                self.assertTrue(telegram_button_label(label).startswith(icon))

    def test_known_long_button_labels_are_compact(self) -> None:
        self.assertEqual(telegram_button_label("Как подать заявление"), "📨 Заявление")
        self.assertEqual(telegram_button_label("Какие документы нужны"), "📄 Документы")
        self.assertEqual(telegram_button_label("Вступительные испытания"), "🧪 Вступительные испытания")
        self.assertEqual(telegram_button_label("Правила приёма в 2026 году"), "📜 Правила 2026")
        self.assertEqual(telegram_button_label("Приёмная кампания 2026/27"), "🧭 Поступление в колледж")
        self.assertEqual(telegram_button_label("Поступление в колледж"), "🧭 Поступление в колледж")
        self.assertEqual(telegram_button_label("Правила приёма 2026/27"), "📜 Правила 2026/27")
        self.assertEqual(telegram_button_label("Льготы при поступлении"), "🎖️ Льготы")
        self.assertEqual(telegram_button_label("Поступление иностранцев"), "🌍 Иностранцы")

    def test_compact_known_buttons_stay_two_per_row(self) -> None:
        markup, _ = scenario_keyboard(
            [
                "Как подать заявление",
                "Какие документы нужны",
                "Вступительные испытания",
                "Поступление в колледж",
            ],
            include_end=False,
        )

        self.assertEqual([len(row) for row in markup.inline_keyboard], [2, 2])

    def test_wide_unknown_button_uses_own_row_and_safe_callback_data(self) -> None:
        long_label = "Очень длинное описание кнопки, которое не помещается в два столбца"
        markup, callback_labels = scenario_keyboard(
            ["Назад", "Главное меню", long_label, "Свой вопрос"],
            include_end=False,
        )

        self.assertEqual([len(row) for row in markup.inline_keyboard], [2, 1, 1])
        wide_button = markup.inline_keyboard[1][0]
        self.assertTrue(wide_button.text.endswith("..."))
        self.assertEqual(callback_labels[wide_button.callback_data], long_label)
        self.assertLessEqual(
            len(wide_button.callback_data.encode("utf-8")),
            TELEGRAM_CALLBACK_DATA_LIMIT,
        )

    def test_start_text_uses_new_ambi_intro(self) -> None:
        text = self.adapter.start_text_html()

        self.assertIn("Привет! Я - Амби", text)
        self.assertIn("AI-амбассадор колледжей Москвы", text)
        self.assertIn("Давай выберем, с чего начать.", text)


if __name__ == "__main__":
    unittest.main()
