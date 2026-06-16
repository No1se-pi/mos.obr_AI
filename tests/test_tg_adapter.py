import unittest

from app.interfaces.tg_adapter import TELEGRAM_SAFE_HTML_LIMIT, TelegramChatAdapter


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


if __name__ == "__main__":
    unittest.main()
