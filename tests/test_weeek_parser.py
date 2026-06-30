import unittest

from scripts.fetch_weeek_knowledge import (
    DEFAULT_ROOT_URL,
    build_documents,
    chunk_article,
    decode_token,
    extract_token,
)


ROOT_TOKEN = "NzA4NTAzfDlkYThiY2Q2LTMwMDctNDAxZi1hODllLTM3YjAyMjc1YTRmNQ=="


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def paragraph(value: str) -> dict:
    return {"type": "paragraph", "content": [text(value)]}


def heading(value: str, level: int = 2) -> dict:
    return {"type": "heading", "attrs": {"level": level}, "content": [text(value)]}


def article_data() -> dict:
    return {
        "content": [
            heading("Льготы"),
            paragraph(
                "Льготы при поступлении помогают абитуриентам использовать "
                "первоочередное или преимущественное право."
            ),
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [paragraph("Нужно подготовить подтверждающие документы.")],
                    }
                ],
            },
        ]
    }


class WeeekParserTest(unittest.TestCase):
    def test_extracts_and_decodes_shared_token(self) -> None:
        token = extract_token(DEFAULT_ROOT_URL)

        self.assertEqual(token, ROOT_TOKEN)
        self.assertEqual(
            decode_token(token),
            ("708503", "9da8bcd6-3007-401f-a89e-37b02275a4f5"),
        )

    def test_chunks_article_blocks(self) -> None:
        chunks = chunk_article("Льготы", article_data())

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["heading"], "Льготы")
        self.assertIn("Льготы при поступлении", chunks[0]["content"])
        self.assertIn("подтверждающие документы", chunks[0]["content"])

    def test_builds_ingest_documents(self) -> None:
        payloads = [
            {
                "token": ROOT_TOKEN,
                "workspace_name": "МЦРПО",
                "article": {"name": "Льготы", "content": {"data": article_data()}},
            }
        ]

        docs = build_documents(
            payloads,
            token_urls={ROOT_TOKEN: DEFAULT_ROOT_URL},
        )

        self.assertEqual(len(docs), 1)
        doc = docs[0]
        metadata = doc["metadata_json"]
        self.assertEqual(doc["doc_type"], "faq")
        self.assertEqual(doc["title"], "Льготы")
        self.assertEqual(metadata["source_type"], "weeek")
        self.assertEqual(metadata["section"], "Льготы")
        self.assertEqual(metadata["workspace_id"], "708503")
        self.assertEqual(metadata["article_id"], "9da8bcd6-3007-401f-a89e-37b02275a4f5")
        self.assertEqual(metadata["category"], "admission_benefits")
        self.assertIn("weeek", metadata["tags"])
        self.assertIn("льготы", metadata["tags"])


if __name__ == "__main__":
    unittest.main()
