from app.ingest.document_builder import build_all_documents
from app.ingest.loader_json import load_json_data
from app.ingest.normalize import normalize_data
from app.logger import setup_logger

setup_logger()


def main() -> None:
    data = load_json_data()
    normalized = normalize_data(data)
    documents = build_all_documents(normalized)

    print(f"Кол-во документов: {len(documents)}")
    print("\nПервый документ:\n")
    print(documents[0])

    print("\nВторой документ:\n")
    print(documents[1])


if __name__ == "__main__":
    main()