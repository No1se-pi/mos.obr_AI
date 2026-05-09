from app.ingest.loader_faq import load_faq_json


def main() -> None:
    data = load_faq_json("data/faq_admission.json")

    print("Количество FAQ:", len(data))
    print()
    print("Первый FAQ:")
    print(data[0])


if __name__ == "__main__":
    main()