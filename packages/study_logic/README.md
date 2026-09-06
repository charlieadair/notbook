# `study-logic` (Python / FastAPI)

S0 study engine mount for DEMO: **one FastAPI process on :8000**. Backend includes this router. There is no second Node server and no proxy.

The TypeScript package in `packages/study-logic` remains as reference/tests. **DEMO must use this FastAPI router.**

## Install

From the repo root:

```bash
pip install -e packages/study_logic
pip install -e 'packages/study_logic[dev]'   # pytest + httpx
```

## Backend mount (DEMO)

Recommended — inject Backend’s in-process retrieve (same chunk fields as `POST /api/v1/notebooks/{id}/retrieve`):

```python
from fastapi import FastAPI
from study_logic.api import install_study_logic

def retrieve(notebook_id: str, query: str, top_k: int = 8):
    # Backend vault callable — return chunks with
    # id, source_id, text, locator, score, source_filename
    return backend_vault.search(notebook_id, query, top_k)

app = FastAPI()
install_study_logic(app, retrieve=retrieve, prefix="/api/v1")
# app now serves study routes on :8000 under /api/v1
```

Equivalent include:

```python
from fastapi import FastAPI
from study_logic.api import create_router, router

app = FastAPI()

# Production: pass Backend retrieve
app.include_router(create_router(retrieve=retrieve), prefix="/api/v1")

# Offline fixture only (nb_bio):
# from study_logic.api import router
# app.include_router(router, prefix="/api/v1")
```

`router` is fixture-backed. DEMO should pass `retrieve=` so quizzes cite the real vault.

HTTP-client retrieve (if Backend is already serving retrieve on the same app, prefer the in-process callable instead):

```python
from study_logic.vault import HttpVaultRetrieve
from study_logic.api import create_router

app.include_router(
    create_router(retrieve=HttpVaultRetrieve("http://127.0.0.1:8000").retrieve),
    prefix="/api/v1",
)
```

## Routes (after `prefix="/api/v1"`)

| Method | Path |
| --- | --- |
| `POST` | `/api/v1/notebooks/{id}/topics/propose` |
| `POST` | `/api/v1/notebooks/{id}/topics/confirm` |
| `GET` | `/api/v1/notebooks/{id}/topics` |
| `POST` | `/api/v1/notebooks/{id}/quizzes` |
| `POST` | `/api/v1/quizzes/{id}/attempts` |
| `GET` | `/api/v1/notebooks/{id}/scoreboard` |

- **409 `TopicsUnconfirmed`** until the topic map is confirmed.
- **422 `InsufficientEvidence`** if retrieve returns no citable chunks — never invent items.
- Explicit `{ "names": [...] }` on confirm writes already-confirmed topics (skip propose).
- Every quiz item has `citation_chunk_ids` = retrieved `chunk.id`.
- Scoreboard: last **20** attempts / topic, proficiency **0.8**.

## Tests

```bash
cd packages/study_logic
pip install -e '.[dev]'
pytest
```
