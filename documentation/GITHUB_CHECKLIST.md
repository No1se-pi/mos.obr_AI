# Чеклист перед загрузкой на GitHub

## Проверить, что НЕ загружаем

- `.env`
- `venv/`
- `local_cache/`
- `logs/`
- большие модели
- приватные токены
- персональные данные пользователей

---

## Проверить, что загружаем

- исходный код `app/`
- `data/` с демонстрационными JSON
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env.example`
- документацию:
  - `README.md`
  - `ARCHITECTURE.md`
  - `API.md`
  - `USER_GUIDE.md`
  - `DEPLOYMENT.md`
  - `DEMO_SCRIPT.md`
  - `LOGS.md`
  - `TROUBLESHOOTING.md`

---

## Команды Git

```bash
git init
git add .
git commit -m "Initial project version"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

---

## Проверка после загрузки

Открыть репозиторий в браузере и проверить:
- README красиво отображается;
- нет `.env`;
- нет `venv`;
- нет `local_cache`;
- нет логов пользователей;
- документация понятна.
