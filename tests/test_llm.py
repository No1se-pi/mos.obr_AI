from app.logger import setup_logger
from app.llm.ollama_client import OllamaClient

setup_logger()


def main():
    client = OllamaClient()

    response = client.generate("Привет! Кто ты?")
    print("\nОтвет модели:\n")
    print(response)


if __name__ == "__main__":
    main()