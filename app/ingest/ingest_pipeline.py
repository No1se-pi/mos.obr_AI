from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import Document
from app.ingest.document_builder import build_all_documents
from app.ingest.loader_faq import load_faq_json
from app.ingest.loader_json import load_json_data
from app.ingest.normalize import normalize_data
from app.logger import get_logger
from app.rag.embedder import Embedder

logger = get_logger(__name__)
settings = get_settings()


def run_ingest(db: Session) -> None:
    logger.info("Запуск ingest pipeline...")

    # 1. Основные данные колледжей
    colleges_raw = load_json_data()
    normalized_colleges = normalize_data(colleges_raw)
    college_documents = build_all_documents(normalized_colleges)

    # 2. FAQ
    faq_documents = load_faq_json(settings.faq_data_path)

    # 3. Объединяем всё
    all_documents = college_documents + faq_documents
    logger.info(f"Всего документов для ingest: {len(all_documents)}")

    # 4. Embedder
    embedder = Embedder()

    # 5. Чистим таблицу
    logger.info("Очистка таблицы documents...")
    db.execute(delete(Document))
    db.commit()
    logger.info("Таблица documents очищена")

    # 6. Загружаем документы
    total = len(all_documents)

    for idx, doc in enumerate(all_documents, start=1):
        embedding = embedder.encode(doc["title"] + "\n" + doc["content"])

        db_doc = Document(
            doc_type=doc["doc_type"],
            title=doc["title"],
            content=doc["content"],
            metadata_json=doc["metadata_json"],
            embedding_json=embedding,
        )
        db.add(db_doc)

        if idx % 50 == 0 or idx == total:
            db.commit()
            logger.info(f"Загружено документов: {idx}/{total}")

    logger.info("Ingest pipeline завершён")