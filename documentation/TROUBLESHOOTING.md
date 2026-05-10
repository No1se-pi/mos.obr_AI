# Troubleshooting

## Контейнер долго стоит на загрузке embedding-модели

Если видно:

```text
Load pretrained SentenceTransformer: BAAI/bge-m3
```

и дальше долго нет логов, значит модель загружается или считаются embeddings.

Что проверить:

```bash
docker compose logs -f app
```

Модель `BAAI/bge-m3` тяжёлая, первый запуск может быть долгим.

---

## Проверить кеш модели

В контейнере:

```bash
docker compose exec app bash
du -sh /app/local_cache/*
```

Если `sentence_transformers/models--BAAI--bge-m3` весит около 1GB, модель скачана.

---

## Проверить Ollama

На хосте:

```bash
ollama list
ollama run qwen2.5:7b-instruct
```

Если Ollama на Windows, в Docker нужно использовать:

```env
OLLAMA_HOST=http://host.docker.internal:11434
```

---

## API отвечает Not Found

Проверь, что поднят сервис `api`:

```bash
docker compose ps
```

Проверь routes:

```bash
docker compose exec api python -c "from app.interfaces.api import app; print([r.path for r in app.routes])"
```

---

## Логи не скачиваются

Проверь:

```text
http://localhost:8000/api/logs/list
```

Если папка пустая, значит сервис API не видит volume с логами.

---

## Бот отвечает не по теме

Нужно смотреть логи и проверять:
- какой режим выбрал router;
- какие документы вернул retriever;
- какой prompt ушёл в LLM.

Чаще всего проблема находится в одном из трёх мест:
- router выбрал неправильный режим;
- retriever нашёл нерелевантные документы;
- LLM добавила лишние обобщения.
