from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import Document
from app.ingest.document_builder import build_all_documents
from app.ingest.loader_faq import load_faq_json
from app.ingest.loader_json import load_json_data
from app.ingest.loader_weeek import load_weeek_knowledge_json
from app.ingest.normalize import normalize_data
from app.ingest.reference_indexes import write_reference_indexes
from app.ingest.source_fingerprint import (
    DATA_FINGERPRINT_METADATA_KEY,
    DATA_FINGERPRINT_VERSION,
    DATA_FINGERPRINT_VERSION_METADATA_KEY,
    current_data_fingerprint,
)
from app.logger import get_logger
from app.rag.embedder import Embedder

logger = get_logger(__name__)
settings = get_settings()


def run_ingest(db: Session) -> None:
    logger.info("Запуск ingest pipeline...")

    # 1. Основные данные колледжей
    colleges_raw = load_json_data()
    normalized_colleges = normalize_data(colleges_raw)
    write_reference_indexes(normalized_colleges, Path(settings.data_path).parent)
    college_documents = build_all_documents(normalized_colleges)

    # 2. FAQ
    faq_documents = load_faq_json(settings.faq_data_path)

    # 3. Публичная база знаний Weeek
    weeek_documents = load_weeek_knowledge_json(settings.weeek_knowledge_path)

    # 4. Объединяем всё
    all_documents = college_documents + faq_documents + weeek_documents
    logger.info(f"Всего документов для ingest: {len(all_documents)}")
    data_fingerprint = current_data_fingerprint(settings)
    logger.info("Data fingerprint for ingest: %s", data_fingerprint)

    # 5. Embedder
    embedder = Embedder()

    # 6. Сначала считаем embeddings, не трогая рабочую таблицу.
    # Так API продолжает видеть старую базу, пока новая версия документов готовится.
    total = len(all_documents)
    prepared_documents: list[Document] = []
    for idx, doc in enumerate(all_documents, start=1):
        embedding = embedder.encode(doc["title"] + "\n" + doc["content"])
        metadata_json = dict(doc["metadata_json"])
        metadata_json[DATA_FINGERPRINT_METADATA_KEY] = data_fingerprint
        metadata_json[DATA_FINGERPRINT_VERSION_METADATA_KEY] = DATA_FINGERPRINT_VERSION

        prepared_documents.append(
            Document(
                doc_type=doc["doc_type"],
                title=doc["title"],
                content=doc["content"],
                metadata_json=metadata_json,
                embedding_json=embedding,
            )
        )

        if idx % 50 == 0 or idx == total:
            logger.info(f"Подготовлено документов: {idx}/{total}")

    # 7. Заменяем документы одной транзакцией. При сбое старая база не исчезает.
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
