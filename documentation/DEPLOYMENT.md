# Деплой И Запуск

Проект рассчитан на запуск через Docker Compose. Compose поднимает три сервиса:
- `db` - PostgreSQL;
- `api` - FastAPI для сайта и web-демо;
- `app` - Telegram-бот или CLI, в зависимости от `APP_ENTRYPOINT`.

Ollama по умолчанию запускается отдельно на хосте.

## 1. Подготовить Окружение

Нужно установить:
- Docker Desktop;
- Ollama;
- Git;
- модель Ollama, например `qwen2.5:7b-instruct`.

```powershell
ollama pull qwen2.5:7b-instruct
ollama list
```

## 2. Создать .env

```powershell
Copy-Item .env.example .env
```

Минимально проверь:

```env
OLLAMA_MODEL=qwen2.5:7b-instruct
TELEGRAM_BOT_TOKEN=your_token
API_LOGS_ENABLED=false
```

Для Docker Desktop на Windows compose использует:

```env
DOCKER_OLLAMA_HOST=http://host.docker.internal:11434
```

## 3. Собрать Контейнеры

```powershell
docker compose build
```

После изменения кода:

```powershell
docker compose build app api
docker compose up -d
```

Полная пересборка без кеша:

```powershell
docker compose build --no-cache app api
docker compose up -d
```

## 4. Запустить

```powershell
docker compose up -d
```

Проверить:

```powershell
docker compose ps
docker compose logs -f api
```

## 5. Первый Запуск И Ingest

При `BOOTSTRAP_INGEST=auto` сервис `app` проверяет документы в БД. Если документов нет, он запускает загрузку данных и расчет embeddings.

Первый запуск может идти долго из-за:
- скачивания `BAAI/bge-m3`;
- расчета embeddings;
- записи документов в PostgreSQL.

Если база уже заполнена, ingest пропускается.

## 6. Проверить API

```text
http://localhost:8000/api/health
http://localhost:8000/docs
http://localhost:8000/api/demo
```

В `/api/health` смотри:
- `database_ready`;
- `documents_ready`;
- `rag_ready`;
- `ollama_ready`;
- `documents_total`.

## 7. Включить Debug-Логи API

По умолчанию ручки логов закрыты.

Для локальной диагностики:

```env
API_LOGS_ENABLED=true
API_LOGS_TOKEN=secret
```

Перезапуск:

```powershell
docker compose up -d
```

Запрос:

```powershell
curl -H "Authorization: Bearer secret" http://localhost:8000/api/logs/list
```

## 8. Остановить

```powershell
docker compose down
```

Остановить и удалить volume PostgreSQL:

```powershell
docker compose down -v
```

`down -v` удалит базу и заставит проект заново делать ingest при следующем запуске.

## 9. Production-Замечания

Перед публичным запуском стоит:
- не включать `/api/logs/*` без токена;
- хранить `.env` вне репозитория;
- поставить reverse proxy и HTTPS;
- ограничить CORS;
- добавить Alembic-миграции;
- перевести embeddings на pgvector;
- настроить мониторинг и резервные копии PostgreSQL.
