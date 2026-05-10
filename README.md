# mosobr-ai

## Requirements

- Docker Desktop
- Ollama
- Python 3.11+ (optional for local run)

## Quick Start

```powershell
docker compose up --build
```

После запуска:

- API: http://localhost:8000/docs
- Demo chat: http://localhost:8000/api/demo

## Docker

Перед запуском проверь `.env`: токены не попадают в образ, но используются compose как runtime-переменные.

По умолчанию контейнер запускает Telegram-бота, Postgres поднимается отдельным сервисом, Ollama ожидается на хосте:

```powershell
docker compose up --build
```

Если Ollama доступна не на хосте Docker Desktop, задай адрес явно:

```powershell
$env:DOCKER_OLLAMA_HOST="http://host.docker.internal:11434"
docker compose up --build
```

Если локальный Postgres уже занимает порт 5432:

```powershell
$env:POSTGRES_HOST_PORT="5433"
docker compose up --build
```

Первый запуск может быть долгим: при пустой БД `BOOTSTRAP_INGEST=auto` создаёт таблицы и загружает embeddings.
