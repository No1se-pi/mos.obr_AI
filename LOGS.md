# Как забрать логи из Docker

## Вариант 1: через API

Если API-сервис запущен на `localhost:8000`, открой в браузере:

```text
http://localhost:8000/api/logs/download
```

API отдаст архив `mosobr_logs_YYYYMMDD_HHMMSS.tar.gz` со всеми файлами из папки `/app/logs` внутри контейнера.

Посмотреть список файлов логов:

```text
http://localhost:8000/api/logs/list
```

Важно: этот endpoint сделан для локального демо. В публичный интернет его нельзя оставлять без авторизации.

## Вариант 2: через docker compose

Из корня проекта:

```powershell
docker compose cp app:/app/logs ./exported_logs
```

Если сервис с API называется `api`, можно забрать логи так:

```powershell
docker compose cp api:/app/logs ./exported_logs
```

## Вариант 3: посмотреть логи контейнера

```powershell
docker compose logs -f app
```

или API:

```powershell
docker compose logs -f api
```
