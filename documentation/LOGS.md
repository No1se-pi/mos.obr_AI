# Логи

Логи нужны для отладки качества ответов, router, RAG и поведения пользователей.

## Где Лежат

В репозитории:

```text
logs/
```

В контейнерах:

```text
/app/logs
```

Compose монтирует локальную папку:

```yaml
volumes:
  - ./logs:/app/logs
```

## Какие Логи Есть

- `logs/web_sessions/*.jsonl` - web/API диалоги в машинном формате.
- `logs/web_sessions/*.txt` - web/API диалоги в удобном текстовом виде.
- `logs/telegram_sessions/*.jsonl` - Telegram диалоги.
- `logs/telegram_sessions/*.txt` - Telegram диалоги текстом.
- обычные stdout/stderr логи контейнеров через `docker compose logs`.

## Защита API-Логов

Ручки логов закрыты по умолчанию:

```env
API_LOGS_ENABLED=false
```

Если ручка выключена, API возвращает `403`.

Включить локально:

```env
API_LOGS_ENABLED=true
API_LOGS_TOKEN=secret
```

Если `API_LOGS_TOKEN` задан, нужен bearer token:

```powershell
curl -H "Authorization: Bearer secret" http://localhost:8000/api/logs/list
```

Скачать архив:

```powershell
curl -L -H "Authorization: Bearer secret" -o mosobr_ai_logs.zip http://localhost:8000/api/logs/download
```

## Через Docker

Смотреть поток логов:

```powershell
docker compose logs -f
docker compose logs -f app
docker compose logs -f api
```

Скопировать папку из контейнера, если volume не использовался:

```powershell
docker compose ps
docker cp <container_name>:/app/logs ./exported_logs
```

## Как Анализировать

Полезно смотреть:
- какой `mode` выбрал router;
- сохранился ли `session_id`;
- есть ли повторяющиеся ошибки Ollama;
- какие запросы ушли в fallback;
- где ответ вышел за границы базы;
- какие FAQ или aliases нужно добавить.

Логи могут содержать реальные пользовательские сообщения. Не публикуй их в открытом репозитории.
