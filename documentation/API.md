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
  "session_id": null,
  "route": null,
  "action": null,
  "user_type": null
}
```

Response:

```json
{
  "session_id": "uuid",
  "mode": "college",
  "answer": "...",
  "route": "college",
  "step": "college_found",
  "suggestions": [
    {"label": "Контакты и адреса", "action": "college_contacts"},
    {"label": "Все специальности", "action": "college_specialties"},
    {"label": "Порядок поступления", "action": "college_admission"},
    {"label": "Главное меню", "action": "main_menu"}
  ],
  "suggestion_labels": [
    "Контакты и адреса",
    "Все специальности",
    "Порядок поступления",
    "Главное меню"
  ],
  "expired_previous_session": false
}
```

`session_id` нужно хранить на стороне сайта и передавать в следующих запросах. Так бот понимает уточнения: "подробнее", "давай проще", "а какие еще колледжи?".

### Сценарные Поля

`route` и `action` необязательны. Старый клиент может отправлять только `user_id`, `message`, `session_id`: API продолжит через сценарный роутинг, а для пустого первого сообщения покажет приветствие и главное меню.

`suggestions` возвращаются как массив объектов `{label, action}`. `label` можно показать на кнопке, `action` нужно отправлять в следующий `/api/chat` вместе с `message` и `session_id`. Для старых UI дополнительно есть `suggestion_labels` - список только из текстов кнопок.

Поддерживаемые `route`:
- `college` - выбор или поиск колледжа.
- `profession` - выбор профессии, отрасли или специальности.
- `admission` - FAQ по поступлению.
- `custom` - свой вопрос с перенаправлением в подходящий маршрут.

`user_type`:
- `parent` - родитель, более официальный тон.
- `applicant` - абитуриент, более простой тон.

Частые `action`:
- `set_user_type_parent`, `set_user_type_applicant`;
- `route_college`, `route_profession`, `route_admission`, `route_custom`;
- `industry:education`, `industry:it`;
- `pick:1`, `pick:2`, `pick:3`;
- `show_more_specialties`, `show_more_colleges`;
- `main_menu`, `back`.

Пример route-based запроса:

```json
{
  "user_id": "site_user_123",
  "session_id": "optional",
  "message": "КАИТ 20",
  "route": "college",
  "action": "search_college",
  "user_type": "applicant"
}
```

Пример ответа:

```json
{
  "session_id": "uuid",
  "mode": "profession",
  "answer": "В отрасли «Педагогика и работа с детьми» могут подойти такие специальности...",
  "route": "profession",
  "step": "industry_specialties",
  "suggestions": [
    {"label": "1. Подробнее", "action": "pick:1"},
    {"label": "2. Подробнее", "action": "pick:2"},
    {"label": "Показать ещё специальности", "action": "show_more_specialties"},
    {"label": "Главное меню", "action": "main_menu"}
  ],
  "suggestion_labels": [
    "1. Подробнее",
    "2. Подробнее",
    "Показать ещё специальности",
    "Главное меню"
  ],
  "expired_previous_session": false
}
```

Состояние маршрута хранится на backend в `chat_sessions.metadata_json`. Минимальные поля:
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

Открывает HTML-демо сценарного web-виджета:

```text
http://localhost:8000/api/demo
```

## GET /static/mosobr-widget.js

Отдаёт чистый JS-виджет без React и сборщика. Пример вставки:

```html
<script src="http://localhost:8000/static/mosobr-widget.js"></script>

<script>
  MosobrWidget.init({
    apiUrl: "http://localhost:8000/api/chat",
    title: "AI - Амбассадор профессий Амби"
  });
</script>
```

## Сложные Запросы И FAQ

`/api/chat` умеет обрабатывать сообщения, где есть несколько смыслов. Например запрос про `МПК`, педагогику и преимущества за олимпиады будет разобран на основной блок про колледж/направление и отдельный блок про поступление.

Запросы про особые основания, подтверждение статуса и первоочередное право зачисления отвечают кратко и осторожно: бот сообщает, что категорию нужно подтверждать официальными документами, а точные правила и перечень документов нужно проверять в приёмной комиссии колледжа.

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
