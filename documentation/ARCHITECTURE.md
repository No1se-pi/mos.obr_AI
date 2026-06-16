# Архитектура

`mosobr_ai` - локальный AI-помощник по колледжам Москвы. Он не дообучает LLM, а использует RAG: сначала ищет факты в локальной базе, потом просит модель сформулировать ответ.

## Поток Запроса

```text
Пользователь
  -> Telegram / HTTP API / CLI
  -> ChatService
  -> DialogRouter
  -> Retriever / reference catalog
  -> Ollama
  -> ответ пользователю
```

## Основные Компоненты

`app/interfaces/api.py`

FastAPI-приложение:
- `/api/chat`;
- `/api/health`;
- `/api/demo`;
- `/api/session/close`;
- `/api/session/reset`;
- защищенные `/api/logs/list` и `/api/logs/download`.

`app/interfaces/telegram_bot.py`

Telegram UI: `/start`, кнопка начала диалога, кнопка завершения сессии, защита от параллельных сообщений во время генерации.

`app/interfaces/tg_adapter.py`

Связывает Telegram с `ChatService`, форматирует HTML-ответы и пишет Telegram-логи.

`app/services/chat_service.py`

Главная бизнес-логика:
- создает и читает сессии;
- сохраняет историю сообщений;
- вызывает router;
- выбирает RAG, catalog или scripted fallback;
- обрабатывает уточнения по истории;
- ограничивает ответы фактами из базы.

`app/services/dialog_router.py`

Выбирает режим диалога:
- `script`;
- `recommend_colleges`;
- `faq`;
- `detail`;
- `detail_more`;
- `career_guidance`;
- `chat`;
- `out_of_scope`.

У router есть hard rules для безопасности, FAQ и известных сценариев. LLM используется только как дополнительный классификатор, а критичные решения перепроверяются постобработкой.

`app/rag/retriever.py`

Ищет документы по базе. Сейчас используется гибридный подход:
- embedding cosine similarity;
- keyword score;
- domain score;
- anchor rules;
- штрафы против нерелевантных вузов/институтов.

Важно: `pgvector` установлен как зависимость, но текущая схема хранит embeddings в JSON-поле `documents.embedding_json`. Настоящий vector-тип и индекс пока не включены.

`app/services/reference_catalog.py`

Быстрый справочник поверх подготовленных JSON:
- профессия -> колледжи;
- отрасль -> профессии;
- контакты колледжей;
- список специальностей.

`app/ingest/`

Pipeline загрузки данных:
1. читает `data/colleges.json` и `data/faq_admission.json`;
2. нормализует записи;
3. собирает документы колледжей, специальностей и FAQ;
4. считает embeddings;
5. записывает документы в PostgreSQL;
6. обновляет `profession_colleges.json` и `industry_professions.json`.

`app/llm/ollama_client.py`

HTTP-клиент к локальной Ollama. Генерация настроена с низкой temperature, чтобы уменьшить случайные фантазии.

## База Данных

PostgreSQL хранит:
- `documents` - RAG-документы;
- `chat_sessions` - сессии;
- `chat_messages` - историю сообщений.

Таблицы создаются через SQLAlchemy `create_all`. Alembic-миграций пока нет.

## Безопасность

Есть несколько уровней защиты:
- hard rules для опасных и незаконных запросов;
- запрет пошаговых инструкций для вреда;
- ограничение домена: колледжи Москвы, поступление, профориентация;
- fallback при недостатке фактов;
- закрытые debug-логи через `API_LOGS_ENABLED` и `API_LOGS_TOKEN`;
- `.env` и логи исключены из git.

## Ограничения

- Нет production-миграций Alembic.
- Нет настоящего pgvector-индекса.
- Ollama должна быть запущена отдельно.
- RAG снижает риск галлюцинаций, но не гарантирует абсолютную точность.
- Актуальность зависит от обновления JSON-данных.
