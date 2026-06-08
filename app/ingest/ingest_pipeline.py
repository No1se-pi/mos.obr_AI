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

    # 5. Сначала считаем embeddings, не трогая рабочую таблицу.
    # Так API продолжает видеть старую базу, пока новая версия документов готовится.
    total = len(all_documents)
    prepared_documents: list[Document] = []
    for idx, doc in enumerate(all_documents, start=1):
        embedding = embedder.encode(doc["title"] + "\n" + doc["content"])

        prepared_documents.append(
            Document(
                doc_type=doc["doc_type"],
                title=doc["title"],
                content=doc["content"],
                metadata_json=doc["metadata_json"],
                embedding_json=embedding,
            )
        )

        if idx % 50 == 0 or idx == total:
            logger.info(f"Подготовлено документов: {idx}/{total}")

    # 6. Заменяем документы одной транзакцией. При сбое старая база не исчезает.
    try:
        logger.info("Замена документов в БД одной транзакцией...")
        db.execute(delete(Document))
        db.add_all(prepared_documents)
        db.commit()
        logger.info(f"Загружено документов в БД: {total}")
    except Exception:
        db.rollback()
        logger.exception("Ingest failed; transaction rolled back")
        raise

    logger.info("Ingest pipeline завершён")
