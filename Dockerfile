FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/local_cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/local_cache/sentence_transformers

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --default-timeout=120 --retries=10 \
       --extra-index-url https://download.pytorch.org/whl/cpu \
       -r requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/local_cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/local_cache/sentence_transformers \
    HF_HUB_DISABLE_XET=1 \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4
       
COPY app ./app
COPY data ./data

RUN mkdir -p /app/logs/telegram_sessions /app/local_cache/huggingface /app/local_cache/sentence_transformers

CMD ["python", "-m", "app.bootstrap"]


