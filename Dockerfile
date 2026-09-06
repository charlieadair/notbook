# syntax=docker/dockerfile:1
# All-in-one local demo: Study API :8000 + Web UI :3000. Tesseract included.
FROM node:22-alpine AS web
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

COPY --from=web /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/notbook.conf
COPY packages/study_logic /app/packages/study_logic
COPY backend /app/backend
COPY docker/start.sh /start.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/packages/study_logic /app/backend \
    && chmod +x /start.sh \
    && mkdir -p /data

ENV DATA_DIR=/data \
    INFERENCE_PROVIDER=stub \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["/start.sh"]
