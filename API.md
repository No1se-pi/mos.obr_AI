# API для сайта

API нужен для подключения AI-помощника к сайту или демо-виджету. Полноценный фронтенд не требуется: сайт отправляет HTTP-запросы, API возвращает ответ ИИ и `session_id`.

## Запуск

```bash
uvicorn app.interfaces.api:app --host 0.0.0.0 --port 8000
```

В Docker API запускается отдельным сервисом `api` и доступен на:

```text
http://localhost:8000
```

Демо-страница:

```text
http://localhost:8000/api/demo
```

Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

## Проверка состояния

```http
GET /api/health
```

Пример ответа:

```json
{
  "status": "ok",
  "service": "mosobr-ai-api",
  "active_site_sessions": 1,
  "session_ttl_minutes": 30
}
```

## Отправка сообщения

```http
POST /api/chat
```

Тело запроса:

```json
{
  "user_id": "site_user_123",
  "message": "Расскажи про КАИТ 20",
  "session_id": null
}
```

Ответ:

```json
{
  "session_id": "uuid-сессии",
  "mode": "detail",
  "answer": "Ответ помощника...",
  "expired_previous_session": false
}
```

`session_id` нужно сохранить на стороне сайта, например в `localStorage`, и отправлять в следующих запросах.

## Закрытие сессии

```http
POST /api/session/close
```

```json
{
  "user_id": "site_user_123",
  "session_id": "uuid-сессии"
}
```

## Сброс сессии

```http
POST /api/session/reset
```

```json
{
  "user_id": "site_user_123",
  "session_id": "uuid-сессии"
}
```

## TTL сессии

API хранит активную web-сессию в памяти. Если пользователь не пишет больше 30 минут, при следующем сообщении старая сессия считается устаревшей, и будет создана новая.

История диалога всё равно сохраняется в базе через существующий `session_service`.
