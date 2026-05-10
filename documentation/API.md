# API

API сделан на FastAPI и предназначен для подключения сайта или чат-виджета.

Базовый адрес локально:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

## GET /api/health

Проверка работоспособности API.

### Пример ответа

```json
{
  "status": "ok"
}
```

---

## POST /api/chat

Отправить сообщение в ИИ.

### Request

```json
{
  "user_id": "site_user_123",
  "message": "Расскажи про КАИТ 20",
  "session_id": null
}
```

### Response

```json
{
  "session_id": "uuid",
  "mode": "detail",
  "answer": "..."
}
```

`session_id` нужно сохранять на стороне сайта, чтобы продолжать диалог в той же сессии.

---

## POST /api/session/close

Закрыть сессию.

### Request

```json
{
  "user_id": "site_user_123",
  "session_id": "uuid"
}
```

### Response

```json
{
  "status": "closed"
}
```

---

## POST /api/session/reset

Сбросить сессию и начать новую.

### Request

```json
{
  "user_id": "site_user_123"
}
```

### Response

```json
{
  "status": "reset"
}
```

---

## GET /api/demo

Простая HTML-демка чат-окна.

```text
http://localhost:8000/api/demo
```

---

## GET /api/logs/list

Показать список доступных логов.

### Response

```json
{
  "logs_dir": "/app/logs",
  "exists": true,
  "files": [
    {
      "path": "telegram_sessions/123.txt",
      "size_bytes": 1024
    }
  ]
}
```

---

## GET /api/logs/download

Скачать все логи zip-архивом.

```text
http://localhost:8000/api/logs/download
```

---

## TTL сессий

Для web/API-сессий используется TTL. Если пользователь долго не пишет, старая сессия считается устаревшей и может быть заменена новой.

Это нужно, чтобы незакрытые сессии не жили бесконечно.
