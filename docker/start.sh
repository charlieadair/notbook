#!/bin/sh
# All-in-one demo: nginx :3000 (UI) + uvicorn :8000 (Study API).
set -eu
mkdir -p "${DATA_DIR:-/data}"
nginx
cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
