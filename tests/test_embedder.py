from app.logger import setup_logger
from app.rag.embedder import Embedder

setup_logger()


def main() -> None:
    embedder = Embedder()

    text = "Хочу стать программистом"
    vector = embedder.encode(text)

    print("Текст:", text)
    print("Размер вектора:", len(vector))
    print("Первые 10 чисел:", vector[:10])


if __name__ == "__main__":
    main()