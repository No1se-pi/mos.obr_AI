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
- История сессий, follow-up память и route state для сценарного UX.
- Сценарный режим с выбором роли: `Родитель` или `Абитуриент / поступающий`.
- 4 основных маршрута: выбор колледжа, выбор профессии, порядок поступления, свой вопрос.
- Telegram inline-кнопки и web-виджет с такими же маршрутами.
- `suggestions` с понятными `label/action` для API, web и Telegram callback.
- Пагинация `Показать ещё специальности` и `Показать ещё колледжи` без повторов.
- Обработка сложных запросов: колледж + направление + поступление/льготы не теряются.
- FAQ про СВО и первоочередное право зачисления с осторожной формулировкой.
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

## Сценарный UX

Новая сессия начинается с выбора роли:
- `Родитель` - более официальный тон, обращение на вы, больше структуры.
- `Абитуриент / поступающий` - простой дружелюбный тон, обращение на ты.

После выбора роли пользователь попадает в главное меню:
1. Выбрать колледж
2. Выбрать профессию
3. Узнать о порядке поступления
4. Свой вопрос

В Telegram эти шаги показываются inline-кнопками. Нажатие обрабатывается через стабильные callback action-коды, например `route_profession`, `industry:education`, `pick:1`, `show_more_specialties`, `main_menu`.

Сценарии хранят состояние в `chat_sessions.metadata_json`: `user_type`, `current_route`, `route_step`, `last_college`, `last_profession`, `last_industry`, `last_specialty`, `last_results`, `last_answer`, `tone_mode`.

Для педагогики приоритет получают дошкольное образование, преподавание в начальных классах, коррекционная педагогика и педагогика дополнительного образования. Вокал и музыка не попадают в топ без явного музыкального запроса. Запросы про хакинг, пентест и кибербезопасность направляются в IT/ИБ/сети, а не в случайные производственные специальности.

## Web-Виджет

Демо доступно по адресу:

```text
http://localhost:8000/api/demo
```

Виджет использует те же маршруты и `label/action`-кнопки, что и API. На demo-странице есть блок с кодом вставки и кнопка `Скопировать`, которая копирует HTML/JS-код виджета в буфер обмена.

Для вставки на сайт:

```html
<script src="http://localhost:8000/static/mosobr-widget.js"></script>

<script>
  MosobrWidget.init({
    apiUrl: "http://localhost:8000/api/chat",
    title: "AI-помощник по колледжам"
  });
</script>
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
