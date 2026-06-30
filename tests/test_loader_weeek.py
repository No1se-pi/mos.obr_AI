import json
import tempfile
import unittest
from pathlib import Path

from app.ingest.loader_weeek import load_weeek_knowledge_json


class WeeekLoaderTest(unittest.TestCase):
    def test_missing_file_returns_empty_list(self) -> None:
        self.assertEqual(load_weeek_knowledge_json("missing_weeek_knowledge.json"), [])

    def test_loads_document_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "weeek.json"
            payload = [
                {
                    "doc_type": "faq",
                    "title": "Льготы",
                    "content": "Текст",
                    "metadata_json": {"source_type": "weeek"},
                }
            ]
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(load_weeek_knowledge_json(str(path)), payload)

    def test_rejects_non_list_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "weeek.json"
            path.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_weeek_knowledge_json(str(path))


if __name__ == "__main__":
    unittest.main()
