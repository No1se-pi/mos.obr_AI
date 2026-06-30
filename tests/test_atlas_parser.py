import unittest

from app.ingest.document_builder import build_specialty_documents
from app.ingest.normalize import normalize_college
from scripts.fetch_atlas_data import (
    extract_specialty_links,
    merge_colleges,
    parse_college_page,
    parse_faq_page,
    parse_specialty_page,
)


ATLAS = "https://colleges.shkolamoskva.ru/atlas"


class AtlasParserTest(unittest.TestCase):
    def test_extract_specialty_links_ignores_clusters_and_colleges(self) -> None:
        html = """
        <a href="/atlas/cluster/it">IT</a>
        <a href="/atlas/informaczionnye-sistemy-i-programmirovanie">Информационные системы</a>
        <a href="https://colleges.shkolamoskva.ru/atlas/college/it-moskva">ИТ.Москва</a>
        <a href="/atlas/fullmap">Карта</a>
        """

        links = extract_specialty_links(html, ATLAS)

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["name"], "Информационные системы")
        self.assertEqual(links[0]["url"], f"{ATLAS}/informaczionnye-sistemy-i-programmirovanie")

    def test_parse_specialty_page_reads_professions_and_colleges(self) -> None:
        html = """
        <h1>Колледжи Москвы</h1>
        <h1>Разработка и управление программным обеспечением (Программист)</h1>
        <div class="examples-name">Разработчик программного обеспечения</div>
        <a class="college-link" href="https://colleges.shkolamoskva.ru/atlas/college/it-moskva">ИТ.Москва</a>
        """

        parsed = parse_specialty_page(
            html,
            f"{ATLAS}/informaczionnye-sistemy-i-programmirovanie",
            cluster={"key": "it", "title": "Информационные технологии"},
        )

        self.assertEqual(parsed["name"], "Разработка и управление программным обеспечением (Программист)")
        self.assertIn("Разработчик программного обеспечения", parsed["professions"])
        self.assertIn("Программист", parsed["professions"])
        self.assertEqual(parsed["colleges"][0]["name"], "ИТ.Москва")
        self.assertEqual(parsed["cluster_key"], "it")

    def test_parse_college_page_reads_contacts_addresses_and_directions(self) -> None:
        html = """
        <h1>Колледжи Москвы</h1>
        <h1>ИТ.Москва</h1>
        <h2>Выбери направление</h2>
        <a href="https://colleges.shkolamoskva.ru/atlas/veb-razrabotka">Веб-разработка</a>
        <a href="https://colleges.shkolamoskva.ru/atlas/veb-razrabotka?from_college=486">
          ЮАО, улица Академика Миллионщикова 20, м. Каширская
        </a>
        <h2>Контакты</h2>
        <a href="tel:+74951234567">+7 (495) 123-45-67</a>
        <a href="mailto:info@example.ru">info@example.ru</a>
        <a href="https://itmoscow.mskobr.ru/">Сайт колледжа</a>
        <h2>Адреса учебных корпусов</h2>
        <p>ЮАО, Судостроительная улица 48, м. Нагатинский затон</p>
        """

        parsed = parse_college_page(html, "https://colleges.shkolamoskva.ru/atlas/college/it-moskva")

        self.assertEqual(parsed["name"], "ИТ.Москва")
        self.assertEqual(parsed["website"], "https://itmoscow.mskobr.ru/")
        self.assertIn("+7 (495) 123-45-67", parsed["contacts"])
        self.assertIn("info@example.ru", parsed["contacts"])
        self.assertIn("Веб-разработка", [item["name"] for item in parsed["specialties"]])
        self.assertTrue(any("Миллионщикова" in item for item in parsed["addresses"]))
        self.assertTrue(any("Судостроительная" in item for item in parsed["addresses"]))

    def test_merge_colleges_preserves_existing_and_adds_atlas_url(self) -> None:
        existing = [
            {
                "name": "ИТ.Москва",
                "aliases": ["ИТ"],
                "specialties": [{"name": "Старая специальность", "professions": ["Старый профиль"]}],
                "addresses": [],
                "contacts": [],
                "website": "",
            }
        ]
        incoming = [
            {
                "name": "ИТ.Москва",
                "aliases": [],
                "specialties": [
                    {
                        "name": "Веб-разработка",
                        "professions": ["Веб-разработчик"],
                        "atlas_url": f"{ATLAS}/veb-razrabotka",
                    }
                ],
                "addresses": ["ЮАО, улица Академика Миллионщикова 20"],
                "contacts": ["info@example.ru"],
                "website": "https://itmoscow.mskobr.ru",
                "atlas_url": f"{ATLAS}/college/it-moskva",
            }
        ]

        merged, stats = merge_colleges(existing, incoming)

        self.assertEqual(stats["updated_colleges"], 1)
        self.assertEqual(len(merged), 1)
        names = [item["name"] for item in merged[0]["specialties"]]
        self.assertIn("Старая специальность", names)
        self.assertIn("Веб-разработка", names)
        self.assertEqual(merged[0]["atlas_url"], f"{ATLAS}/college/it-moskva")

    def test_faq_parser_reads_details(self) -> None:
        html = """
        <details>
          <summary>Как подать заявление?</summary>
          <p>Заявление подается через mos.ru.</p>
        </details>
        """

        docs = parse_faq_page(html, "https://school.mos.ru/mcrpo/portal/admission/")

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["title"], "Как подать заявление?")
        self.assertIn("mos.ru", docs[0]["content"])
        self.assertEqual(docs[0]["metadata_json"]["source_type"], "school_mos_admission")

    def test_atlas_url_survives_normalize_and_document_building(self) -> None:
        college = {
            "name": "ИТ.Москва",
            "aliases": [],
            "specialties": [
                {
                    "name": "Веб-разработка",
                    "professions": ["Веб-разработчик"],
                    "atlas_url": f"{ATLAS}/veb-razrabotka",
                }
            ],
            "addresses": [],
            "contacts": [],
            "website": "",
            "atlas_url": f"{ATLAS}/college/it-moskva",
        }

        normalized = normalize_college(college)
        docs = build_specialty_documents(normalized)

        self.assertEqual(normalized["specialties"][0]["atlas_url"], f"{ATLAS}/veb-razrabotka")
        self.assertEqual(docs[0]["metadata_json"]["specialty_url"], f"{ATLAS}/veb-razrabotka")


if __name__ == "__main__":
    unittest.main()
