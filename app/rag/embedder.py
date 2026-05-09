import os
import warnings

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

warnings.filterwarnings(
    "ignore",
    message="Using `TRANSFORMERS_CACHE` is deprecated",
    category=FutureWarning,
)


class Embedder:
    def __init__(self) -> None:
        if settings.hf_home:
            os.environ["HF_HOME"] = settings.hf_home

        if settings.sentence_transformers_home:
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = settings.sentence_transformers_home

        logger.info(f"Загрузка embedding модели: {settings.embedding_model}")
        self.model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding модель успешно загружена")

    def encode(self, text: str) -> list[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def get_dimension(self) -> int:
        sample_vector = self.encode("тест")
        return len(sample_vector)