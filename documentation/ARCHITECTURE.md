# Архитектура

`mosobr_ai` - локальный AI-помощник поступления в колледжи Москвы. Он не дообучает LLM, а использует RAG: сначала ищет факты в локальной базе, потом просит модель сформулировать ответ.

## Поток Запроса

```text
Пользователь
  -> Telegram / HTTP API / CLI
  -> ScenarioService для кнопочных маршрутов
  -> ChatService
  -> DialogRouter
  -> Retriever / reference catalog
  -> Ollama
  -> ответ пользователю
```

## Основные Компоненты

`app/interfaces/api.py`

FastAPI-приложение:
- `/ambi/v1/dialog` - основной публичный endpoint диалога;
- `/api/health`;
- `/api/demo`;
- `/ambi/v1/session/close`;
- `/ambi/v1/session/reset`;
- защищенные `/api/logs/list` и `/api/logs/download`.

`app/interfaces/telegram_bot.py`

Telegram UI: `/start`, inline-кнопки сценариев, callback action-коды, кнопка завершения сессии, защита от параллельных сообщений во время генерации.

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

`app/services/scenario_service.py`

Сценарный UX-слой поверх `ChatService`:
- начинает новую сессию с приветствия и главного меню без отдельного выбора роли;
- хранит `current_route` и `route_step`;
- ведёт 4 маршрута: колледж, профессия, поступление, свой вопрос;
- отдаёт `suggestions`/`suggestion_buttons` для Telegram inline-кнопок, API и web-виджета;
- использует существующие методы `ChatService` для фактов: поиск колледжа, контакты, все специальности, FAQ и RAG;
- хранит `last_results`, `offset` и тип списка, чтобы кнопки `Показать ещё специальности` и `Показать ещё колледжи` продолжали старый поиск без повторов;
- применяет продуктовые правила: работа с детьми ведёт в педагогику, ювелирные интересы ведут в ювелирные/ремесленные варианты, педагогика не ранжирует вокал без музыкального контекста, хакинг/пентест ведут в IT/ИБ/сети, сложные запросы делятся на смысловые блоки;
- добавляет связанные темы после FAQ-ответов в маршруте поступления и отдельно различает общий вопрос про вступительные испытания и ОВЗ/специальные условия.

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

`chat_sessions.metadata_json` хранит route state:
- `user_type`
- `current_route`
- `route_step`
- `last_college`
- `last_profession`
- `last_industry`
- `last_specialty`
- `last_results`
- `last_answer`
- `tone_mode`

Таблицы создаются через SQLAlchemy `create_all`. Alembic-миграций пока нет. Для локальной совместимости после добавления `metadata_json` на старте выполняется idempotent-проверка схемы и `ALTER TABLE`, если колонка отсутствует.

## Интерфейсы

Telegram:
- `/start` показывает приветствие и кнопки главного меню;
- дальнейшие ответы получают inline-кнопки из `ScenarioService.suggestion_buttons`;
- callback data хранит короткие action-коды: `route_profession`, `industry:education`, `pick:1`, `show_more_colleges`, `main_menu`;
- есть кнопка `Завершить сессию`.

HTTP API:
- `/ambi/v1/dialog` принимает формат `user_id/message/session_id`; старый `/api/chat` оставлен как отключаемый legacy-алиас;
- дополнительно поддерживает `route`, `action`, `user_type`;
- возвращает `route`, `step`, `suggestions` как `{label, action}` и `suggestion_labels` для совместимости.

Web demo:
- `/api/demo` открывает страницу с живым виджетом;
- `/static/mosobr-widget.js` отдаёт чистый JS-виджет без React и сборщика;
- виджет показывает кнопку в правом нижнем углу, окно чата, сценарные action-кнопки, поле ввода, главное меню, завершение сессии и блок копирования кода вставки.

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
