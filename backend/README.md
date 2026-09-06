# Notbook Study API (backend)

Local vault for Notbook S0: notebooks, ingest, inspectable chunks, retrieve, inference adapter.

See [ARCHITECTURE.md](ARCHITECTURE.md) for stack choices.

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
uvicorn app.main:app --reload --port 8000
```

- API: http://127.0.0.1:8000/api/v1
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Adapter (no secrets): http://127.0.0.1:8000/inference

Data defaults to `./data/notbook.db` and `./data/files/{notebook_id}/`. Override with `NOTBOOK_DATA_DIR`.

Default inference is **stub** (hash embeddings + fixed JSON complete). To use an OpenAI-compatible server:

```bash
export INFERENCE_ADAPTER=openai-compatible
export OPENAI_API_BASE=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=sk-...
# optional:
# export OPENAI_EMBED_MODEL=...
# export OPENAI_CHAT_MODEL=...
```

Never commit API keys.

## Tests

```bash
cd backend
pip install -e ".[dev]"
pytest
```

## Smoke (Release)

With the server running:

```bash
# 1. Create notebook
NOTEBOOK=$(curl -s -X POST http://127.0.0.1:8000/api/v1/notebooks \
  -H 'content-type: application/json' \
  -d '{"title":"Linear Algebra"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# 2. Ingest paste
curl -s -X POST "http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK/sources/paste" \
  -H 'content-type: application/json' \
  -d '{"filename":"notes.txt","text":"The spectral theorem: a real symmetric matrix is orthogonally diagonalizable."}'

# 3. List sources (must show extract_status + chunk_count — not just upload OK)
curl -s "http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK/sources"

# 4. List chunks for the first source
SOURCE=$(curl -s "http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK/sources" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')
curl -s "http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK/sources/$SOURCE/chunks"

# 5. Retrieve (chunk ids are citation_chunk_ids)
curl -s -X POST "http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"spectral theorem","top_k":8}'
```

Same path works for file upload (`pdf|md|txt|png|jpg|jpeg|webp`) at `POST /api/v1/notebooks/{id}/sources/upload`.
