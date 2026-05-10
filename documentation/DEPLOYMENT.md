# Запуск и развёртывание

## Запуск через Docker

### 1. Собрать контейнеры

```bash
docker compose build
```

### 2. Запустить

```bash
docker compose up -d
```

### 3. Проверить

```bash
docker compose ps
```

### 4. Смотреть логи

```bash
docker compose logs -f
```

---

## Пересборка после изменений

Если менялся код:

```bash
docker compose build app api
docker compose up -d
```

Если нужно полностью пересобрать без кеша:

```bash
docker compose build --no-cache app api
docker compose up -d
```

---

## Остановка

```bash
docker compose down
```

---

## Что делает Dockerfile

`Dockerfile` описывает, как собрать контейнер приложения:

1. берёт Python-образ;
2. копирует проект;
3. устанавливает зависимости из `requirements.txt`;
4. задаёт рабочую папку;
5. запускает нужную команду.

---

## Что делает docker-compose.yml

`docker-compose.yml` запускает несколько сервисов вместе:

- `db` — PostgreSQL;
- `app` — Telegram-бот / основной сервис;
- `api` — FastAPI-интерфейс для сайта.

Также compose задаёт:
- порты;
- переменные окружения;
- volumes;
- зависимости между сервисами.

---

## Volumes

Volumes нужны, чтобы данные не пропадали после пересоздания контейнера.

Обычно сохраняются:
- PostgreSQL data;
- logs;
- local_cache.

---

## Ollama

Если Ollama запущена на Windows-хосте, внутри Docker нужно обращаться к ней через:

```text
http://host.docker.internal:11434
```

В `.env`:

```env
OLLAMA_HOST=http://host.docker.internal:11434
```

---

## Частые команды

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f api
docker compose logs -f db
docker compose restart
docker compose down
docker compose up -d
```
