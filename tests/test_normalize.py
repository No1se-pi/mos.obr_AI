from app.ingest.loader_json import load_json_data
from app.ingest.normalize import normalize_data
from app.logger import setup_logger

setup_logger()


def main():
    data = load_json_data()
    normalized = normalize_data(data)

    print("\nДо нормализации:")
    print(data[0]["specialties"][0]["name"])

    print("\nПосле нормализации:")
    print(normalized[0]["specialties"][0]["name"])


if __name__ == "__main__":
    main()