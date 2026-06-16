# API

API реализован на FastAPI и нужен для подключения web-чата, демонстрации и технической диагностики.

Базовый адрес локально:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

## GET /api/health

Показывает состояние API, базы, документов RAG и Ollama. Healthcheck не падает, если Ollama недоступна: API остается живым, а `ollama_ready` будет `false`.

Пример ответа:

```json
{
  "status": "ok",
  "service": "mosobr-ai-api",
  "database_ready": true,
  "documents_ready": true,
  "rag_ready": true,
  "ollama_ready": true,
  "ollama_model": "qwen2.5:7b-instruct",
  "active_site_sessions": 1,
  "session_ttl_minutes": 30,
  "api_logs_enabled": false,
  "api_logs_token_required": false,
  "documents_total": 300,
  "documents_faq": 63,
  "documents_college": 68,
  "documents_specialty": 169
}
```

Поля:
- `database_ready` - API может подключиться к PostgreSQL.
- `documents_ready` - в базе есть FAQ, колледжи и специальности.
- `rag_ready` - база и документы готовы для поиска.
- `ollama_ready` - Ollama отвечает на короткий `/api/tags`.
- `ollama_model` - модель из `.env`.

## POST /api/chat

Отправляет сообщение пользователя в AI-сервис.

Request:

```json
{
  "user_id": "site_user_123",
  "message": "Расскажи про КАИТ 20",
  "session_id": null
}
```

Response:

```json
{
  "session_id": "uuid",
  "mode": "detail",
  "answer": "..."
}
```

`session_id` нужно хранить на стороне сайта и передавать в следующих запросах. Так бот понимает уточнения: "подробнее", "давай проще", "а какие еще колледжи?".

## POST /api/session/close

Закрывает web/API-сессию пользователя.

Request:

```json
{
  "user_id": "site_user_123",
  "session_id": "uuid"
}
```

Response:

```json
{
  "ok": true,
  "message": "Сессия закрыта"
}
```

## POST /api/session/reset

Сбрасывает текущую web/API-сессию. Следующее сообщение создаст новую сессию.

Request:

```json
{
  "user_id": "site_user_123",
  "session_id": "uuid"
}
```

Response:

```json
{
  "ok": true,
  "message": "Новая сессия будет создана при следующем сообщении"
}
```

## GET /api/demo

Открывает HTML-демо web-чата:

```text
http://localhost:8000/api/demo
```

## GET /api/logs/list

Показывает список лог-файлов. Ручка закрыта по умолчанию.

Чтобы включить:

```env
API_LOGS_ENABLED=true
API_LOGS_TOKEN=secret
```

Если token задан, нужен заголовок:

```text
Authorization: Bearer secret
```

Пример:

```powershell
curl -H "Authorization: Bearer secret" http://localhost:8000/api/logs/list
```

## GET /api/logs/download

Отдает zip-архив с логами. Доступ защищается так же, как `/api/logs/list`.

```powershell
curl -L -H "Authorization: Bearer secret" -o logs.zip http://localhost:8000/api/logs/download
```

## TTL Сессий

Для web/API-сессий используется TTL 30 минут. Если пользователь долго молчит, старая web-сессия считается устаревшей, а следующий запрос может создать новую.
