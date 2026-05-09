from app.ingest.loader_json import load_json_data
from app.logger import setup_logger

setup_logger()


def main() -> None:
    data = load_json_data()

    print(f"Количество записей: {len(data)}")
    print("\nПервая запись:\n")
    print(data[0])


if __name__ == "__main__":
    main()