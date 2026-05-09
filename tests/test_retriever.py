from app.db.session import SessionLocal
from app.logger import setup_logger
from app.rag.retriever import Retriever

setup_logger()


def main() -> None:
    db = SessionLocal()
    try:
        retriever = Retriever()

        queries = [
            "Какие документы нужны для поступления?",
            "Как подать заявление через mos.ru?",
            "Есть ли отсрочка от армии?",
            "Можно ли поступить в вуз после колледжа без ЕГЭ?",
        ]

        for query in queries:
            print("=" * 80)
            print("Запрос:", query)
            print()

            results = retriever.search(db, query, top_k=5, diversify_by_college=False)

            for i, doc in enumerate(results[:3], start=1):
                print(f"--- Результат {i} ---")
                print("Тип:", doc.doc_type)
                print("Заголовок:", doc.title)
                print("Категория:", doc.metadata_json.get("category"))
                print("Раздел:", doc.metadata_json.get("section"))
                print()
    finally:
        db.close()


if __name__ == "__main__":
    main()