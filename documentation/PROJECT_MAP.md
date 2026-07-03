# Карта Проекта mosobr_ai

Эта заметка объясняет, зачем нужна каждая папка и каждый файл в проекте. Ее можно читать как технический конспект.

## 1. Главная Идея

`mosobr_ai` - локальный AI-помощник поступления в колледжи Москвы: профориентация, выбор колледжа и вопросы поступления.

Система не дообучает языковую модель. Вместо этого она использует RAG:

1. Берет данные из `data/*.json`.
2. Превращает колледжи, специальности и FAQ в документы.
3. Считает embeddings.
4. Кладет документы в PostgreSQL.
5. При вопросе пользователя ищет релевантные документы.
6. Формирует ответ через scripted logic, reference catalog или Ollama.

Главная цель: отвечать по локальной базе и не выдумывать колледжи, которых нет в данных.

## 2. Как Идет Один Запрос

```text
Пользователь
  -> Telegram / Web API / CLI
  -> ChatService
  -> SessionService достает историю
  -> DialogRouter выбирает режим
  -> ReferenceCatalog или Retriever ищет факты
  -> ChatService формирует ответ
  -> Ollama подключается только там, где нужен живой текст
  -> ответ сохраняется в историю и логи
```

Ключевые режимы:

- `script` - приветствие, безопасность, служебные ответы.
- `faq` - документы, поступление, ОВЗ, льготы, mos.ru.
- `detail` - подробности колледжа или специальности.
- `detail_more` - продолжение прошлой темы.
- `recommend_colleges` - подбор колледжей.
- `career_guidance` - профориентация.
- `chat` - короткая реакция без RAG.
- `out_of_scope` - темы вне проекта.

## 3. Корень Проекта

### `.github/`

Папка для GitHub Actions.

### `.github/workflows/ci.yml`

CI-пайплайн. Запускается на `push` и `pull_request`.

Что делает:
- ставит Python 3.11;
- устанавливает `requirements.txt`;
- устанавливает `ruff`;
- запускает `ruff check . --select E9,F63,F7,F82`;
- запускает `python -m unittest discover -s tests`;
- собирает Docker-образ через `docker build .`;
- создает временный `.env` из `.env.example`;
- проверяет compose через `docker compose config --quiet`.

Зачем нужен: GitHub сам проверяет, что новый коммит не сломал тесты, синтаксис и Docker-сборку.

### `.dockerignore`

Говорит Docker, что не надо отправлять в build context.

Исключает:
- `.env`;
- `venv/`;
- `logs/`;
- `local_cache/`;
- IDE-файлы;
- кеш Python.

Зачем нужно: образ получается меньше, секреты и логи не попадают внутрь сборки.

### `.env`

Локальный файл настроек. В git не должен попадать.

Там обычно лежат:
- токен Telegram;
- адрес Ollama;
- настройки PostgreSQL;
- настройки API;
- флаги логов.

### `.env.example`

Безопасный шаблон `.env`, который можно хранить в git.

Команда:

```powershell
Copy-Item .env.example .env
```

После копирования в `.env` нужно поставить настоящий `TELEGRAM_BOT_TOKEN`.

### `.gitignore`

Говорит git, какие локальные файлы не отслеживать.

Главное:
- `.env`;
- `venv/`;
- `logs/`;
- `local_cache/`;
- `__pycache__/`;
- временные архивы.

### `Dockerfile`

Инструкция сборки Python-образа приложения.

Блоки:
- берет `python:3.11-slim`;
- ставит системные зависимости;
- копирует `requirements.txt`;
- ставит Python-зависимости;
- копирует `app/` и `data/`;
- создает папки логов и кеша;
- запускает `python -m app.bootstrap`.

### `docker-compose.yml`

Описывает три сервиса:

- `db` - PostgreSQL 16.
- `api` - FastAPI на порту `8000`.
- `app` - Telegram-бот или CLI.

Важные моменты:
- оба Python-сервиса используют один Dockerfile;
- `api` запускается командой `uvicorn app.interfaces.api:app`;
- `app` запускает `app.bootstrap`;
- Ollama ожидается на хосте через `DOCKER_OLLAMA_HOST`;
- `logs/` монтируется в `/app/logs`;
- `model_cache` хранит скачанные модели.

### `README.md`

Главная краткая инструкция проекта:
- что это за проект;
- как запустить;
- какие есть ограничения;
- где документация;
- какие проверки запускать.

### `requirements.txt`

Список Python-зависимостей.

Основные группы:

- LLM:
  - `ollama`;
  - `requests`.
- Конфиг:
  - `python-dotenv`;
  - `pydantic`;
  - `pydantic-settings`.
- База:
  - `sqlalchemy`;
  - `psycopg[binary]`;
  - `pgvector`.
- RAG:
  - `sentence-transformers`;
  - `transformers`;
  - `numpy`.
- Интерфейсы:
  - `python-telegram-bot`;
  - `fastapi`;
  - `uvicorn[standard]`.

Важно: `pgvector` установлен, но текущая схема пока хранит embeddings в JSON и считает cosine similarity в Python.

## 4. Папка `app/`

Главный исходный код приложения.

### `app/main.py`

Простой entrypoint для CLI-режима.

Что делает:
- настраивает logger;
- запускает `run_cli_chat()`.

Используется, если нужно пообщаться с ботом из терминала без Telegram/API.

### `app/bootstrap.py`

Главный entrypoint Docker-сервиса `app`.

Блоки:
- `wait_for_database()` - ждет PostgreSQL;
- `document_count()` и `document_type_count()` - проверяют, есть ли документы;
- `maybe_run_ingest()` - запускает ingest, если база пустая или нет FAQ;
- `main()` - создает таблицы, запускает ingest и выбирает интерфейс.

Переменная `APP_ENTRYPOINT`:
- `telegram` - запуск Telegram-бота;
- `cli` - запуск CLI.

### `app/config.py`

Настройки проекта через `pydantic-settings`.

Читает:
- `.env`;
- переменные окружения Docker;
- настройки CI.

Главная модель: `Settings`.

Важное свойство:
- `postgres_url` - собирает строку подключения к PostgreSQL.

### `app/logger.py`

Настройка логирования.

Зачем нужно:
- единый формат логов;
- управление уровнем логов через `LOG_LEVEL`;
- `get_logger(__name__)` во всех модулях.

## 5. `app/core/`

### `app/core/singletons.py`

Место для общих singleton-объектов.

Зачем нужно: тяжелые объекты вроде модели embeddings или сервиса чата лучше не создавать заново на каждый запрос.

## 6. `app/db/`

Папка базы данных.

### `app/db/session.py`

Создает SQLAlchemy engine и `SessionLocal`.

Отвечает за:
- подключение к PostgreSQL;
- фабрику сессий БД;
- helper `get_db()`.

### `app/db/repository.py`

Описывает базовую таблицу RAG-документов.

Главное:
- `Base` - общий declarative base;
- `Document` - таблица `documents`;
- `create_tables()` - создает таблицы;
- `add_document()` - добавляет документ в БД.

Поля `Document`:
- `doc_type` - `college`, `specialty`, `faq`;
- `title` - заголовок;
- `content` - текст для поиска;
- `metadata_json` - структурные данные;
- `embedding_json` - embedding-вектор.

### `app/db/chat_models.py`

Таблицы истории диалога.

`ChatSession`:
- хранит `session_id`;
- хранит `user_id`;
- связывает сообщения в один диалог.

`ChatMessage`:
- роль `user`, `assistant` или `system`;
- текст сообщения;
- время создания.

Зачем нужно: бот помнит уточнения вроде "подробнее" и "давай проще".

## 7. `app/ingest/`

Папка загрузки и подготовки данных.

### `app/ingest/loader_json.py`

Читает `data/colleges.json`.

Задача: загрузить исходный JSON колледжей в Python-структуры.

### `app/ingest/loader_faq.py`

Читает `data/faq_admission.json`.

Задача: загрузить FAQ по поступлению.

### `app/ingest/normalize.py`

Нормализует данные.

Обычно это:
- приведение строк;
- чистка пустых значений;
- подготовка aliases;
- единый формат списков.

### `app/ingest/document_builder.py`

Превращает сырые данные колледжей и FAQ в RAG-документы.

Создает документы типов:
- `college`;
- `specialty`;
- `faq`.

Также добавляет metadata:
- название колледжа;
- специальность;
- профессии;
- контакты;
- domain tags.

### `app/ingest/ingest_pipeline.py`

Главный pipeline загрузки.

Шаги:
1. загрузить JSON;
2. построить документы;
3. посчитать embeddings через `Embedder`;
4. очистить старые документы;
5. записать новые в PostgreSQL;
6. обновить справочные JSON-индексы.

### `app/ingest/reference_indexes.py`

Строит быстрые справочники:
- `profession_colleges.json`;
- `industry_professions.json`.

Зачем нужно: для простых запросов "где учат на X" иногда надежнее ответить по структурному индексу, а не отдавать все LLM.

## 8. `app/rag/`

Папка поиска по базе знаний.

### `app/rag/embedder.py`

Загружает SentenceTransformers-модель.

По умолчанию:

```text
BAAI/bge-m3
```

Методы:
- `encode(text)` - превращает текст в embedding;
- `get_dimension()` - возвращает размерность embedding.

### `app/rag/retriever.py`

Главный RAG-поиск.

Как считает релевантность:
- `cosine_similarity` по embeddings;
- keyword overlap;
- domain score;
- anchor score;
- бонусы для FAQ или specialty;
- штрафы для нерелевантных вузов/институтов;
- точные совпадения колледжей и aliases.

Функция `search()`:
- получает запрос;
- считает embedding запроса;
- достает документы из БД;
- скорит каждый документ;
- сортирует;
- по возможности диверсифицирует по колледжам.

### `app/rag/reranker.py`

Место для будущего reranking-слоя.

Сейчас основная логика ранжирования находится в `retriever.py`.

## 9. `app/llm/`

### `app/llm/ollama_client.py`

HTTP-клиент к Ollama.

Метод:
- `generate(prompt)` - отправляет prompt в `/api/generate`.

Настройки генерации:
- низкая `temperature`;
- ограничение `num_predict`;
- `repeat_penalty`.

Зачем: уменьшить творческий шум и длинные неконтролируемые ответы.

## 10. `app/services/`

Главная бизнес-логика.

### `app/services/chat_service.py`

Самый важный файл проекта.

Отвечает за:
- создание сессии;
- чтение истории;
- вызов router;
- выбор сценария ответа;
- вызов RAG;
- прямые ответы из базы;
- fallback-и;
- защиту от галлюцинаций;
- сохранение ответа в историю.

Крупные блоки:

- college helpers - поиск колледжа по aliases и данным БД;
- contacts - ответы про контакты колледжа;
- specialty details - ответы про специальности;
- history parsing - понимание "второй вариант", "подробнее", "давай проще";
- prompt builders - промпты для recommendation/detail/FAQ/context;
- scripted responses - безопасные шаблонные ответы;
- `ask()` - главная функция обработки пользовательского запроса.

### `app/services/dialog_router.py`

Маршрутизатор диалога.

Задача: определить, что пользователь хочет.

Сначала идут hard rules:
- опасные запросы;
- оскорбления;
- FAQ;
- колледжи;
- follow-up;
- профориентация.

Потом может подключаться LLM-классификатор, но критичные решения проверяются постобработкой.

Пример важного правила:
- "Расскажи про Сестринское дело" -> `detail`;
- "Какие документы нужны для поступления?" -> `faq`.

### `app/services/session_service.py`

Работа с сессиями и историей.

Методы:
- `get_or_create_session()`;
- `add_message()`;
- `get_recent_messages()`.

Зачем: без этого бот не понимает короткие продолжения.

### `app/services/reference_catalog.py`

Структурный каталог поверх JSON-индексов.

Используется, когда нужно быстро и надежно ответить:
- какие колледжи связаны с профессией;
- какие профессии входят в отрасль;
- какие специальности есть в колледже.

### `app/services/web_transcript_store.py`

Пишет web/API-диалоги в файлы.

Форматы:
- `.jsonl` - удобно обрабатывать программно;
- `.txt` - удобно читать глазами.

Зачем: анализ качества ответов.

## 11. `app/interfaces/`

Пользовательские интерфейсы.

### `app/interfaces/api.py`

FastAPI-приложение.

Ручки:
- `GET /api/health`;
- `POST /api/chat`;
- `POST /api/session/close`;
- `POST /api/session/reset`;
- `GET /api/demo`;
- `GET /api/logs/list`;
- `GET /api/logs/download`.

Крупные блоки:
- ожидание БД;
- ожидание документов;
- healthcheck Ollama;
- управление web-сессиями;
- запись web-логов;
- защита логов через env-флаг и bearer token.

### `app/interfaces/telegram_bot.py`

Telegram UI.

Отвечает за:
- `/start`;
- `/help`;
- кнопку начала диалога;
- кнопку завершения сессии;
- защиту от параллельной генерации;
- отправку typing action;
- передачу сообщений в `TelegramChatAdapter`.

### `app/interfaces/tg_adapter.py`

Адаптер между Telegram и `ChatService`.

Делает:
- вызывает `ChatService.ask()`;
- форматирует ответ в HTML для Telegram;
- логирует Telegram-сессии;
- экранирует HTML;
- возвращает объект ответа для bot handler.

### `app/interfaces/cli.py`

Простой терминальный чат.

Зачем: можно тестировать ядро без Telegram и API.

### `app/interfaces/demo_chat.html`

HTML-демо web-чата.

Использует `/api/chat`.

Зачем:
- показать API в браузере;
- быстро тестировать web-сценарий;
- писать web-логи.

## 12. `data/`

Папка исходных и сгенерированных данных.

### `data/colleges.json`

Главная база колледжей.

Содержит:
- название;
- aliases;
- специальности;
- профессии;
- адреса;
- контакты;
- сайт.

Бот не должен уверенно говорить о колледжах, которых нет в этой базе.

### `data/faq_admission.json`

FAQ по поступлению.

Содержит:
- вопрос;
- ответ;
- category;
- tags;
- metadata.

Используется для документов, ОВЗ, льгот, mos.ru, сроков и похожих тем.

### `data/profession_colleges.json`

Сгенерированный индекс:

```text
профессия -> колледжи
```

Зачем: улучшает ответы на вопросы "где учат на ...".

### `data/industry_professions.json`

Сгенерированный индекс:

```text
отрасль -> профессии
```

Зачем: помогает профориентации и подбору направлений.

## 13. `documentation/`

Папка документации.

### `documentation/README.md`

Навигация по документации.

### `documentation/PROJECT_MAP.md`

Этот файл. Подробная карта проекта.

### `documentation/API.md`

Описание HTTP API:
- endpoints;
- request/response;
- healthcheck;
- защита логов.

### `documentation/ARCHITECTURE.md`

Объясняет архитектуру:
- поток запроса;
- основные компоненты;
- ограничения.

### `documentation/DEPLOYMENT.md`

Инструкция запуска и деплоя:
- Docker Compose;
- `.env`;
- Ollama;
- ingest;
- production-замечания.

### `documentation/LOGS.md`

Документация по логам:
- где лежат;
- какие бывают;
- как скачать;
- почему API логов закрыт.

### `documentation/TROUBLESHOOTING.md`

Типовые проблемы:
- долгий запуск;
- Ollama недоступна;
- Telegram не запускается;
- RAG не видит базу;
- venv на Windows сломан из-за кириллицы в пути.

### `documentation/USER_GUIDE.md`

Как пользоваться ботом:
- Telegram;
- web-demo;
- примеры вопросов.

### `documentation/DEMO_SCRIPT.md`

Сценарий показа проекта.

Зачем: удобно идти по нему на защите.

### `documentation/GITHUB_CHECKLIST.md`

Что проверить перед push:
- нет `.env`;
- нет логов;
- тесты;
- CI.

### `documentation/.env.example`

Копия env-шаблона для документации. Основной шаблон находится в корне проекта: `.env.example`.

### `documentation/.gitignore`

Копия gitignore внутри документации. Сейчас важнее корневой `.gitignore`; этот файл можно считать справочным.

## 14. `scripts/`

### `scripts/export_logs.ps1`

PowerShell-скрипт для выгрузки логов.

Зачем: быстро забрать логи из Docker/локальной папки для анализа.

### `scripts/convert_faq_txt_to_json.py`

Утилита конвертации FAQ из текстового формата в JSON.

Зачем: если FAQ сначала готовится как текст, его можно перевести в формат `data/faq_admission.json`.

## 15. `tests/`

Папка тестов.

### `tests/test_api_logging.py`

Проверяет защиту `/api/logs/*`:
- закрыто по умолчанию;
- работает при `API_LOGS_ENABLED=true`;
- bearer token обязателен, если задан.

### `tests/test_chat_service.py`

Интеграционные проверки `ChatService` с реальной БД/окружением.

### `tests/test_chat_service_regression.py`

Регрессионные тесты качества ответов:
- безопасность;
- follow-up память;
- specialty detail;
- ответы без выдумывания колледжей.

### `tests/test_config.py`

Проверяет загрузку настроек.

### `tests/test_db.py`

Проверяет подключение к БД.

### `tests/test_db_count.py`

Проверяет количество документов в БД.

### `tests/test_dialog_router_regression.py`

Проверяет router:
- опасные запросы;
- FAQ про отсрочку;
- профориентационные follow-up;
- "Сестринское дело" как detail.

### `tests/test_document_builder.py`

Проверяет сборку RAG-документов из данных.

### `tests/test_embedder.py`

Проверяет embedding-модель.

### `tests/test_ingest.py`

Проверяет pipeline загрузки данных.

### `tests/test_loader.py`

Проверяет загрузчик `colleges.json`.

### `tests/test_loader_faq.py`

Проверяет загрузчик FAQ.

### `tests/test_llm.py`

Проверяет клиент LLM/Ollama.

### `tests/test_normalize.py`

Проверяет нормализацию данных.

### `tests/test_repository.py`

Проверяет модели/репозиторий БД.

### `tests/test_retriever.py`

Проверяет RAG-поиск.

### `tests/test_session_service.py`

Проверяет создание сессий и хранение истории.

## 16. Runtime-Папки

Эти папки есть локально, но обычно не должны попадать в git.

### `logs/`

Логи диалогов и технические логи.

### `local_cache/`

Кеш моделей HuggingFace/SentenceTransformers.

### `venv/`

Локальное Python-окружение.

### `.ruff_cache/`

Кеш ruff.

### `.git/`

Служебная папка git.

## 17. Переменные Окружения

Главные переменные:

```env
APP_NAME=MosObr AI
APP_ENV=dev
LOG_LEVEL=INFO
OLLAMA_HOST=http://localhost:11434
DOCKER_OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
EMBEDDING_MODEL=BAAI/bge-m3
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mosobr_ai
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATA_PATH=./data/colleges.json
FAQ_DATA_PATH=./data/faq_admission.json
BOOTSTRAP_INGEST=auto
API_PORT=8000
APP_ENTRYPOINT=telegram
TELEGRAM_BOT_TOKEN=put_your_token_here
API_LOGS_ENABLED=false
API_LOGS_TOKEN=
```

Самое важное:
- `TELEGRAM_BOT_TOKEN` нужен только для Telegram.
- `OLLAMA_HOST` нужен при локальном запуске без Docker.
- `DOCKER_OLLAMA_HOST` нужен внутри Docker Compose.
- `BOOTSTRAP_INGEST=auto` запускает ingest, если база пустая.
- `API_LOGS_ENABLED=false` закрывает debug-логи.

## 18. Docker Коротко

`docker compose build`

Собирает образ приложения.

`docker compose up -d`

Запускает `db`, `api`, `app`.

`docker compose logs -f api`

Смотрит API-логи.

`docker compose logs -f app`

Смотрит Telegram/app-логи.

`docker compose down`

Останавливает контейнеры.

`docker compose down -v`

Останавливает контейнеры и удаляет volume PostgreSQL. После этого ingest пойдет заново.

## 19. Где Что Менять

Добавить колледж:

```text
data/colleges.json
```

Добавить FAQ:

```text
data/faq_admission.json
```

Поменять маршрутизацию сценариев:

```text
app/services/dialog_router.py
```

Поменять качество ответов:

```text
app/services/chat_service.py
app/rag/retriever.py
```

Поменять Telegram UI:

```text
app/interfaces/telegram_bot.py
app/interfaces/tg_adapter.py
```

Поменять HTTP API:

```text
app/interfaces/api.py
```

Поменять Docker:

```text
Dockerfile
docker-compose.yml
.dockerignore
```

Поменять CI:

```text
.github/workflows/ci.yml
```

Поменять документацию:

```text
documentation/
README.md
```

## 20. Как Не Запутаться При Отладке

Если ответ плохой, проверяй по порядку:

1. Есть ли данные в `data/`.
2. Прошел ли ingest.
3. Что показывает `/api/health`.
4. Какой mode выбрал `DialogRouter`.
5. Какие документы вернул `Retriever`.
6. Есть ли `session_id` в следующем запросе.
7. Не недоступна ли Ollama.
8. Не ушел ли ответ в fallback.

Для web/API смотри:

```text
logs/web_sessions/
```

Для Telegram:

```text
logs/telegram_sessions/
```

## 21. Текущее Техническое Состояние

Сильные стороны:
- проект запускается через Docker;
- есть CI;
- есть тесты;
- есть RAG;
- есть Telegram и API;
- есть память сессии;
- есть базовая безопасность;
- debug-логи закрыты по умолчанию.

Что можно улучшать позже:
- заменить JSON embeddings на настоящий pgvector;
- добавить Alembic-миграции;
- вынести части `ChatService` в отдельные модули;
- добавить админ-панель для анализа логов;
- расширить FAQ;
- улучшить автоматическую оценку качества ответов.
