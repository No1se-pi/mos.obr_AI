# mosobr_ai

Локальный AI-помощник по профориентации и колледжам Москвы.

Проект помогает школьнику или абитуриенту:
- подобрать колледжи и специальности из локальной базы;
- получить ответы на частые вопросы о поступлении;
- уточнить контакты и сайт колледжа;
- получить профориентационную подсказку;
- протестировать один и тот же AI-сервис через Telegram-бота, REST API или web-демо.

Система работает локально: данные лежат в JSON и PostgreSQL, поиск идет через RAG, ответы формирует локальная LLM через Ollama. RAG снижает риск галлюцинаций, но не дает абсолютной гарантии точности, поэтому важные правила приема нужно сверять с Атласом профессий, сайтом колледжа или приемной комиссией.

## Что Уже Есть

- FastAPI HTTP API.
- Telegram-бот.
- HTML-демо web-чата.
- Docker Compose для `app`, `api`, `db`.
- Загрузка колледжей и FAQ из `data/`.
- Embeddings на `BAAI/bge-m3`.
- RAG-поиск: semantic similarity + keyword/domain rules.
- Индексы `profession -> colleges` и `industry -> professions`.
- История сессий и follow-up память.
- Логирование web и Telegram диалогов.
- Защита debug-ручек логов через env-флаг и bearer token.
- Расширенный `/api/health`.
- GitHub Actions CI: ruff, unittest, docker build, compose config.

## Важные Ограничения

- `pgvector` есть в зависимостях, но текущий поиск еще хранит embeddings в JSON-поле и считает cosine similarity в Python.
- Ollama не запускается внутри compose по умолчанию. Контейнеры обращаются к Ollama на хосте через `host.docker.internal`.
- Первый запуск может быть долгим: скачивается embedding-модель и строятся векторы.
- Качество ответов зависит от полноты `data/colleges.json` и `data/faq_admission.json`.
- Telegram-бот стартует только при валидном `TELEGRAM_BOT_TOKEN`.

## Быстрый Запуск

1. Скопировать пример переменных окружения:

```powershell
Copy-Item .env.example .env
```

2. Заполнить `.env`:

```env
TELEGRAM_BOT_TOKEN=your_token
OLLAMA_MODEL=qwen2.5:7b-instruct
```

3. Установить и запустить Ollama на компьютере:

```powershell
ollama pull qwen2.5:7b-instruct
ollama list
```

4. Собрать и запустить проект:

```powershell
docker compose build
docker compose up -d
```

5. Проверить состояние:

```powershell
docker compose ps
docker compose logs -f api
```

API:

```text
http://localhost:8000/docs
http://localhost:8000/api/demo
http://localhost:8000/api/health
```

## Основные Команды

```powershell
docker compose up -d
docker compose down
docker compose restart
docker compose logs -f app
docker compose logs -f api
docker compose logs -f db
docker compose build app api
```

## Логи

Логи лежат в `logs/` и монтируются в контейнеры как `/app/logs`.

Ручки логов закрыты по умолчанию:

```env
API_LOGS_ENABLED=false
API_LOGS_TOKEN=
```

Для локального доступа:

```env
API_LOGS_ENABLED=true
API_LOGS_TOKEN=secret
```

Запрос:

```powershell
curl -H "Authorization: Bearer secret" http://localhost:8000/api/logs/list
```

## Документация

- [API](documentation/API.md)
- [Архитектура](documentation/ARCHITECTURE.md)
- [Карта проекта](documentation/PROJECT_MAP.md)
- [Деплой](documentation/DEPLOYMENT.md)
- [Логи](documentation/LOGS.md)
- [Сценарий демо](documentation/DEMO_SCRIPT.md)
- [Пользовательский гайд](documentation/USER_GUIDE.md)
- [Troubleshooting](documentation/TROUBLESHOOTING.md)
- [GitHub checklist](documentation/GITHUB_CHECKLIST.md)

## Проверки

Локально после установки зависимостей:

```powershell
python -m unittest discover -s tests
ruff check . --select E9,F63,F7,F82
docker compose config --quiet
```

В GitHub Actions эти проверки запускаются автоматически на `push` и `pull_request`.
