import requests

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                # Снижает творческий шум и случайные языковые вставки.
                "temperature": 0.2,
                "top_p": 0.85,
                "repeat_penalty": 1.08,
                # Не даём модели разгоняться в огромные простыни.
                "num_predict": 700,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()

            data = response.json()
            return data.get("response", "")

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return ""
