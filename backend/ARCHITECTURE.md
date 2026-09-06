# Notbook Backend — S0 architecture

Minimal self-hosted Study API: local vault + inference adapter. Challenge scope is **S0 only** — no auth, no multi-user, no k8s, no video, no quiz pedagogy.

## Stack (locked)

| Concern | Choice |
| --- | --- |
| Language | Python 3.11+ |
| HTTP | FastAPI (OpenAPI at `/openapi.json`, Swagger at `/docs`) |
| App DB + metadata | SQLite at `{data_dir}/notbook.db` (default `./data/notbook.db`) |
| File store | Local filesystem `{data_dir}/files/{notebook_id}/` |
| Vectors | Embedding `BLOB` on `chunks`; cosine similarity in Python |
| Keyword fallback | SQLite FTS5 (`chunks_fts`) when embeddings are missing or empty |
| PDF text | `pypdf` |
| OCR | `pytesseract` + Pillow (Tesseract must be installed on the host) |
| Inference | `InferenceAdapter` ABC/Protocol — default `StubInference` |

## File store

Uploads and pastes are written under `./data/files/{notebook_id}/{source_id}_{filename}`. `Source.raw_path` is stored relative to `data_dir` (e.g. `files/<notebook_id>/...`) so the vault stays relocatable. Filenames are sanitized (no path traversal).

Override the root with `NOTBOOK_DATA_DIR`.

## Database

SQLAlchemy 2.0 + SQLite. Tables:

- `notebooks` — `id`, `title`, `created_at`
- `sources` — `id`, `notebook_id`, `filename`, `type` (`pdf` \| `markdown` \| `paste` \| `image`), `raw_path`, `extract_status` (`pending` \| `ok` \| `failed`), `error`, `created_at`
- `chunks` — `id` (stable UUID, used as `citation_chunk_ids`), `source_id`, `notebook_id`, `text`, `embedding` (nullable BLOB), `locator` JSON `{page?, char_start?, char_end?, order?, region?}`

Topic / Quiz / Attempt / TopicScore are **not** implemented here (Study-logic).

## Vector / retrieve

1. Query is embedded with the active adapter.
2. Chunks that have vectors are scored with cosine similarity.
3. If embeddings are missing or ranking is empty, FTS5 `MATCH` (bm25) plus a simple term-overlap fallback is used.
4. `POST /api/v1/notebooks/{id}/retrieve` returns `{chunks: [{id, source_id, text, locator, score, source_filename?}]}`.

S0 does not use an external vector database.

## Chunking

~2400-character windows (~500–800 tokens at ~4 chars/token) with 400-character overlap. PDF locators include `page`. Image locators include `region` (`full`) and `order`. Markdown/paste locators include `char_start` / `char_end` / `order`.

## OCR and extract status

- Images (`png` / `jpg` / `jpeg` / `webp`): Tesseract via pytesseract.
- **Tesseract must be installed** on the host (`tesseract-ocr` on Debian/Ubuntu). Python wheels do not bundle the binary.
- If OCR or PDF extract fails, the `Source` row is still created and `extract_status` is set to `failed` with `error` populated. No chunks are written.
- PDFs with no extractable text are `failed` (scanned PDFs should be uploaded as images for S0 OCR).

## Inference adapter

`app/inference/base.py` defines `InferenceAdapter` (ABC) and `InferenceProtocol`:

- `embed(texts) -> list[list[float]]`
- `complete(messages, **kwargs) -> str`

Implementations:

1. **`StubInference`** (default) — deterministic feature-hashed embeddings; `complete` returns a fixed JSON string so Study-logic can develop offline.
2. **`OpenAICompatibleInference`** — HTTP client for `{OPENAI_API_BASE}/embeddings` and `/chat/completions`. Reads `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL`, `OPENAI_CHAT_MODEL`. No vendor is hardcoded in policy/retrieve/ingest code.

Activate the remote adapter with `INFERENCE_PROVIDER=openai-compatible` (or `auto` when base + key are set). `GET /inference` reports the active adapter and model names; it never returns secrets.

Study-logic is mounted on the same FastAPI app (`packages/study_logic`, #6). `app.state.retrieve` is:

```python
def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[Chunk]:
    # keys: id, source_id, text, locator, score, source_filename
```

```python
from study_logic.api import install_study_logic
install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")
```

HTTP `POST /api/v1/notebooks/{id}/retrieve` is a thin wrapper over that same callable. `GET /inference` reports `study_logic_mounted: true`. Quiz pedagogy stays in Study-logic.

## Inspectability

“Upload OK” is not sufficient. Clients can:

- `POST /api/v1/notebooks/{id}/sources` — multipart file **or** JSON paste `{filename?, text}` (content-type / `?kind=paste`)
- `GET /api/v1/notebooks/{id}/sources` — extract status + chunk_count
- `GET /api/v1/sources/{source_id}/chunks` — locators + text (vault browser)
- `GET /api/v1/chunks/{chunk_id}` — full chunk + source metadata

## OpenAPI

FastAPI default docs:

- `/openapi.json`
- `/docs`

A committed snapshot lives at [`docs/openapi.json`](docs/openapi.json). Regenerate with:

```bash
python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" > docs/openapi.json
```
