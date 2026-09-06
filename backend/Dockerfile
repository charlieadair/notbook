# syntax=docker/dockerfile:1
# Study API — vault + study_logic on :8000. Tesseract included for handwriting OCR.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY packages/study_logic /app/packages/study_logic
COPY backend /app/backend

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/packages/study_logic /app/backend \
    && useradd --create-home --uid 1000 notbook \
    && mkdir -p /data \
    && chown -R notbook:notbook /data

USER notbook
ENV DATA_DIR=/data \
    INFERENCE_PROVIDER=stub \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
