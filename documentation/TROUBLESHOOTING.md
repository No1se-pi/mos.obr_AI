# Troubleshooting

## Контейнер Долго Запускается

Если в логах видно:

```text
Load pretrained SentenceTransformer: BAAI/bge-m3
```

это нормально для первого запуска. Модель тяжелая, затем проект считает embeddings.

Проверить:

```powershell
docker compose logs -f app
docker compose logs -f api
```

## Бот Или API Не Видят Базу

Проверить PostgreSQL:

```powershell
docker compose ps
docker compose logs -f db
```

Проверить health:

```text
http://localhost:8000/api/health
```

Если `documents_ready=false`, документы еще не загружены или ingest не прошел.

## Ollama Недоступна

Признаки:
- `/api/health` показывает `ollama_ready=false`;
- ответы могут возвращаться fallback-логикой;
- в логах есть `Ollama error`.

Проверка на хосте:

```powershell
ollama list
ollama run qwen2.5:7b-instruct
```

Для Docker Desktop на Windows:

```env
DOCKER_OLLAMA_HOST=http://host.docker.internal:11434
```

После изменения `.env`:

```powershell
docker compose up -d
```

## Telegram-Бот Не Запускается

Проверить:
- в `.env` есть `TELEGRAM_BOT_TOKEN`;
- токен без пробелов и кавычек;
- контейнер `app` запущен;
- Ollama и БД доступны.

Команды:

```powershell
docker compose logs -f app
docker compose restart app
```

Если нужен только API без Telegram, можно временно поставить:

```env
APP_ENTRYPOINT=cli
```

## API Logs Возвращают 403

Это ожидаемо, если debug-логи выключены.

Включить:

```env
API_LOGS_ENABLED=true
API_LOGS_TOKEN=secret
```

Запрос с токеном:

```powershell
curl -H "Authorization: Bearer secret" http://localhost:8000/api/logs/list
```

## Ответы Не По Теме

Проверить по логам:
- какой режим выбрал `DialogRouter`;
- какие документы нашел `Retriever`;
- был ли `session_id` передан в следующем web-запросе;
- не пустая ли база документов;
- доступна ли Ollama.

Частые причины:
- запрос похож на FAQ и detail одновременно;
- пользователь написал follow-up без сохраненного `session_id`;
- в `data/faq_admission.json` нет нужного ответа;
- в `data/colleges.json` нет колледжа или специальности.

## Запрос "Расскажи Про Сестринское Дело" Уходит В Общий Ответ

Это значит, что router не распознал специальность или база не загружена.

Проверить:

```text
http://localhost:8000/api/health
```

Если `documents_specialty=0`, нужно дождаться ingest или пересоздать БД:

```powershell
docker compose down -v
docker compose up -d
docker compose logs -f app
```

## pip В venv Не Работает Из-За Кириллицы В Пути

На Windows иногда ломается launcher у venv, если путь содержит кириллицу.

Рабочие варианты:
- создать проект в пути без кириллицы, например `D:\code\mos.obr_AI`;
- пересоздать venv;
- запускать зависимости через Docker;
- использовать `python -m pip`, а не `pip`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
