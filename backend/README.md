# Notbook Study API (backend)

Local vault for Notbook S0: notebooks, ingest, inspectable chunks, retrieve, inference adapter.

See [ARCHITECTURE.md](ARCHITECTURE.md) for stack choices. Default base URL: **http://127.0.0.1:8000**

## Requirements

- Python 3.11+
- **Tesseract** on `PATH` for image / handwriting OCR (Python wheels do not bundle the binary):
  - macOS: `brew install tesseract`
  - Debian / Ubuntu: `sudo apt-get install tesseract-ocr`
  - The GHCR Study API image already bakes `tesseract-ocr` (`backend/Dockerfile`). **Release owns that image** — host install is only needed when running from source.

If Tesseract is missing, image ingest still creates a `Source` with `extract_status=failed` and an `error` (honest failure, not silent success). When `tesseract` is on `PATH`, [`fixtures/handwritten_scan.png`](fixtures/handwritten_scan.png) should land `extract_status=ok` with at least one chunk searchable via retrieve.

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../packages/study_logic
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
# export CHUNKING_STRATEGY=auto          # auto | llm | heuristic
# export LLM_CHUNK_TIMEOUT_SECONDS=30
# export LLM_CHUNK_MAX_CHARS=24000
# export LLM_CHUNK_MAX_SLICES=64
```

Never commit API keys. See [`.env.example`](.env.example).

With `INFERENCE_PROVIDER=openai-compatible` and `CHUNKING_STRATEGY=auto` (default), ingest asks the chat model to slice the **whole extracted document** into coherent study units, validates that each slice is grounded in the source, then embeds those slices. Stub adapter, timeout, or unparseable output falls back to the 2400-character heuristic windows so upload still completes.

**Timeouts (S0, issue #35):** upload is synchronous but hard-bounded. PDF extract times out after `PDF_EXTRACT_TIMEOUT_SECONDS` (default 30s) and is also capped by `PDF_MAX_PAGES` / `PDF_MAX_CHARS`. A timeout or pypdf failure still creates the `Source` with `extract_status=failed` and returns **201** (inspect the row; do not hang). Embedding uses HTTP connect + read timeouts on the OpenAI-compatible client plus `EMBED_TIMEOUT_SECONDS` around `embed()`; on failure/timeout chunks are stored without vectors and retrieve uses FTS/keyword. **OpenRouter `:free` embed models can queue or never return** — they must not be allowed to block upload. Override the env vars in [`.env.example`](.env.example) if a local runtime needs a longer budget.

## Tests

```bash
cd backend
pip install -e ../packages/study_logic
pip install -e ".[dev]"
pytest
```

## Smoke (Release)

Default base URL: **http://127.0.0.1:8000**. Fixtures: [`fixtures/sample.pdf`](fixtures/sample.pdf), [`fixtures/handwritten_scan.png`](fixtures/handwritten_scan.png). `./scripts/smoke.sh` asserts image `extract_status=ok` when `tesseract` is on `PATH`; otherwise it prints `OCR_SKIPPED` and continues (smoke still passes). Missing Tesseract is an honest `extract_status=failed`, not silent success.

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

# 4b. Sample recent/representative chunks for topic propose (no scores)
curl -s "$BASE/api/v1/notebooks/$NOTEBOOK/chunks?limit=32"

# 5. Retrieve — stable citation_chunk_ids; empty vault or blank/whitespace query returns []
curl -s -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"spectral theorem","top_k":8}'
```

`POST /sources/upload` and `POST /sources/paste` remain as deprecated aliases.

## Study-logic mount

`packages/study_logic` (merged in #6) is installed with the backend and mounted on the same :8000 process:

```python
from study_logic.api import install_study_logic
install_study_logic(app, retrieve=app.state.retrieve, list_chunks=app.state.list_chunks, prefix="/api/v1")
```

`app.state.retrieve(notebook_id, query, top_k=8)` returns chunks with exact keys `id, source_id, text, locator, score, source_filename`. HTTP retrieve is the same callable. Topic propose uses `app.state.list_chunks(notebook_id, limit=32)` (same shape, no scores) instead of empty-query retrieve. `GET /inference` reports `study_logic_mounted: true`.
