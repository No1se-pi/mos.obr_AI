# GitHub Checklist

## Перед Коммитом

Проверь, что в git не попали:
- `.env`;
- `venv/` или `.venv/`;
- `logs/`;
- `local_cache/`;
- дампы базы;
- токены Telegram;
- пользовательские диалоги.

Команда:

```powershell
git status --short
```

## Что Должно Быть В Репозитории

- `app/`;
- `data/`;
- `tests/`;
- `documentation/`;
- `.github/workflows/ci.yml`;
- `.env.example`;
- `Dockerfile`;
- `docker-compose.yml`;
- `requirements.txt`;
- `README.md`.

## Локальные Проверки

Если зависимости установлены:

```powershell
python -m unittest discover -s tests
ruff check . --select E9,F63,F7,F82
docker compose config --quiet
```

Если локальный venv сломан, GitHub Actions все равно прогонит проверки на чистой Ubuntu-виртуалке.

## GitHub Actions

Workflow запускается на:
- `push`;
- `pull_request`.

Шаги:
- checkout;
- Python 3.11;
- установка `requirements.txt`;
- установка `ruff`;
- critical lint `E9,F63,F7,F82`;
- `python -m unittest discover -s tests`;
- `docker build .`;
- `docker compose config --quiet`.

## После Push

Открой вкладку Actions в GitHub и проверь:
- workflow зеленый;
- нет падения unittest;
- docker build прошел;
- в логах нет случайно напечатанных секретов.
