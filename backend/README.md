# Notbook Study API (backend)

Local vault for Notbook S0: notebooks, ingest, inspectable chunks, retrieve, inference adapter.

See [ARCHITECTURE.md](ARCHITECTURE.md) for stack choices. Default base URL: **http://127.0.0.1:8000**

## Requirements

- Python 3.11+
- **Tesseract** on the host for image/handwriting OCR (`sudo apt-get install tesseract-ocr` on Debian/Ubuntu). If Tesseract is missing, image ingest still creates a `Source` with `extract_status=failed`.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# optional: cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: http://127.0.0.1:8000/api/v1
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Adapter (no secrets): http://127.0.0.1:8000/inference

Data defaults to `./data/notbook.db` and `./data/files/{notebook_id}/`. Override with `DATA_DIR` or `NOTBOOK_DATA_DIR`.

Default inference is **stub** (hash embeddings + fixed JSON complete). To use an OpenAI-compatible server:

```bash
export INFERENCE_PROVIDER=openai-compatible
export OPENAI_API_BASE=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=sk-...
# optional:
# export EMBED_MODEL=...
# export CHAT_MODEL=...
```

Never commit API keys. See [`.env.example`](.env.example).

## Tests

```bash
cd backend
pip install -e ".[dev]"
pytest
```

## Smoke (Release)

Default base URL: **http://127.0.0.1:8000**. Fixtures: [`fixtures/sample.pdf`](fixtures/sample.pdf), [`fixtures/handwritten_scan.png`](fixtures/handwritten_scan.png). Image OCR is `failed` unless Tesseract is installed — that is an honest `extract_status`, not silent success.

One command (server already running):

```bash
./scripts/smoke.sh
```

Or the same sequence by hand:

```bash
BASE=http://127.0.0.1:8000

# 1. Create notebook
NOTEBOOK=$(curl -s -X POST "$BASE/api/v1/notebooks" \
  -H 'content-type: application/json' \
  -d '{"title":"Linear Algebra"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# 2. Upload ×3 — PDF, paste, image — via POST /sources (content-type discriminates)
curl -s -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -F "file=@fixtures/sample.pdf;type=application/pdf"
curl -s -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -H 'content-type: application/json' \
  -d '{"filename":"notes.txt","text":"The spectral theorem: a real symmetric matrix is orthogonally diagonalizable."}'
curl -s -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -F "file=@fixtures/handwritten_scan.png;type=image/png"

# 3. List sources — extract_status + chunk_count (upload-OK-only is a fail)
curl -s "$BASE/api/v1/notebooks/$NOTEBOOK/sources"

# 4. List chunks (Scope path) + get one chunk
SOURCE=$(curl -s "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(next(s["id"] for s in rows if s["chunk_count"]>0))')
curl -s "$BASE/api/v1/sources/$SOURCE/chunks"
CHUNK=$(curl -s "$BASE/api/v1/sources/$SOURCE/chunks" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')
curl -s "$BASE/api/v1/chunks/$CHUNK"

# 5. Retrieve — stable citation_chunk_ids; empty vault/query returns []
curl -s -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"spectral theorem","top_k":8}'
```

`POST /sources/upload` and `POST /sources/paste` remain as deprecated aliases.
