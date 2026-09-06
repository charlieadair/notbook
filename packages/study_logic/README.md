# `study-logic` (Python / FastAPI)

S0 + S1 study engine mount for DEMO: **one FastAPI process on :8000**. Backend includes this router (`install_study_logic` / `create_router`). There is no second Node server and no proxy.

The TypeScript package in `packages/study-logic` remains as reference/tests. **DEMO must use this FastAPI router.** S2 (miss→explain→retest) is out.

## Install

From the repo root:

```bash
pip install -e packages/study_logic
pip install -e 'packages/study_logic[dev]'   # pytest (httpx is a runtime dep for SearXNG)
```

## Backend mount (DEMO)

Recommended — inject Backend’s in-process retrieve (same chunk fields as `POST /api/v1/notebooks/{id}/retrieve`) and sample-chunks (same fields as `GET /api/v1/notebooks/{id}/chunks?limit=32`):

```python
from fastapi import FastAPI
from study_logic.api import install_study_logic

def retrieve(notebook_id: str, query: str, top_k: int = 8):
    # Backend vault callable — return chunks with
    # id, source_id, text, locator, score, source_filename
    return backend_vault.search(notebook_id, query, top_k)

def list_chunks(notebook_id: str, limit: int = 32):
    # Recent/representative chunks — no scores. Used by topic propose.
    return backend_vault.sample(notebook_id, limit)

app = FastAPI()
install_study_logic(app, retrieve=retrieve, list_chunks=list_chunks, prefix="/api/v1")
# app now serves study routes on :8000 under /api/v1
```

Equivalent include:

```python
from fastapi import FastAPI
from study_logic.api import create_router, router

app = FastAPI()

# Production: pass Backend retrieve + sample-chunks
app.include_router(create_router(retrieve=retrieve, list_chunks=list_chunks), prefix="/api/v1")

# Offline fixture only (nb_bio):
# from study_logic.api import router
# app.include_router(router, prefix="/api/v1")
```

`router` is fixture-backed. DEMO should pass `retrieve=` and `list_chunks=` so quizzes cite the real vault and propose does not call retrieve with `query=""`.

HTTP-client fallback (if Backend is already serving retrieve / chunks on the same app, prefer the in-process callables instead):

```python
from study_logic.vault import HttpVaultRetrieve
from study_logic.api import create_router

vault = HttpVaultRetrieve("http://127.0.0.1:8000")
app.include_router(
    create_router(retrieve=vault.retrieve, list_chunks=vault.list_chunks),
    prefix="/api/v1",
)
```

`HttpVaultRetrieve.list_chunks` is `GET /api/v1/notebooks/{id}/chunks?limit=32`. If `retrieve` is a bound `VaultRetrieve.retrieve`, propose reuses that object's `list_chunks` automatically.

## Routes (after `prefix="/api/v1"`)

S0 spine:

| Method | Path |
| --- | --- |
| `POST` | `/api/v1/notebooks/{id}/topics/propose` |
| `POST` | `/api/v1/notebooks/{id}/topics/confirm` |
| `GET` | `/api/v1/notebooks/{id}/topics` |
| `POST` | `/api/v1/notebooks/{id}/quizzes` |
| `POST` | `/api/v1/quizzes/{id}/attempts` |
| `GET` | `/api/v1/notebooks/{id}/scoreboard` |

S1 chat tree (same router / same process):

| Method | Path |
| --- | --- |
| `GET` `POST` | `/api/v1/notebooks/{id}/chats/orchestrator` — idempotent get-or-create |
| `GET` | `/api/v1/notebooks/{id}/chats` |
| `GET` | `/api/v1/notebooks/{id}/spawn-offer` |
| `POST` | `/api/v1/notebooks/{id}/chats/specialists` — `{ "topic_ids": string[] }` |
| `POST` | `/api/v1/chats/{id}/messages` — `{ "role"?, "text"?, "content"?, "generate_quiz"? }` |
| `POST` | `/api/v1/chats/{id}/close` — specialist → orchestrator handoff |
| `GET` | `/api/v1/notebooks/{id}/handoffs` |

- **409 `TopicsUnconfirmed`** until the topic map is confirmed.
- **422 `InsufficientEvidence`** if retrieve returns no citable chunks — never invent items. Propose samples via `list_chunks` / `GET …/chunks` (never `retrieve("")`). Empty vault → `[]`. Chunks with no extractable names → **422**.
- **409 `TooManySpecialists`** if a third open specialist would be created (`max_spawn` = **2**).
- **409 `ChatClosed`** if posting to a closed chat.
- `POST …/messages`: **`text` is canonical**; **`content` is accepted as a Web-compat alias**. If both are present, `text` wins. If neither is present (and `generate_quiz` is not true), the route returns **422**.
- Explicit `{ "names": [...] }` on confirm writes already-confirmed topics (skip propose).
- Every quiz item has `citation_chunk_ids` = retrieved `chunk.id` (including `generate_quiz` on a chat).
- Scoreboard: last **20** attempts / topic, proficiency **0.8**. Shared by orchestrator and specialists — grade via `POST /quizzes/{id}/attempts`.
- Spawn offer is **after pretest scores / attempts only** (empty `candidates` if none — never invented from the topic map), **severe-first**, **≤ 2** candidates. Mild gaps stay on the scoreboard (not hidden). Topics not in the offer may still be opened (soft `warnings[]`).
- Orchestrator is **get-or-create** on notebook open (`GET`/`POST …/chats/orchestrator`, and `GET …/chats`). Spawn is an offer; specialists are never auto-opened.
- `Chat` / `Handoff` live in the study-logic memory store (same process as S0). No Backend SQLite tables for S1.
- Close writes an auto **Handoff** into the orchestrator with a progress summary + `scoreboard_snapshot`. Summary is scoreboard/progress only (no unsourced teaching claims).

Optional `{ "topic_ids": [...] }` on `POST /quizzes` scopes generation; omit it for the S0 whole-notebook pretest.

Optional `{ "supplement": true }` is an **explicit opt-in** for labeled web background (issue #43). Default is vault-only. When true, Study searches confirmed topic names (especially useful when vault evidence is thin), passes `[web]` snippets into generation as a hedge, and still requires vault `citation_chunk_ids`. Items that used web hits include `web_citations[]` (`url`, `title`, `snippet`, `source: "web"`). Unset or down SearXNG → `warnings[]` and vault-only fallback — never invented hits. Chat `generate_quiz` stays vault-only.

### Enable SearXNG (optional)

Study-logic owns the HTTP client (`study_logic.search.SearxngClient`). Backend’s httpx stack is inference-only.

1. Set `SEARXNG_URL` (example: `http://127.0.0.1:8080` on the host, or `http://searxng:8080` on the compose network).
2. Start the optional compose service: `docker compose --profile supplement up searxng` (settings in [`deploy/searxng/settings.yml`](../../deploy/searxng/settings.yml) enable the JSON API).
3. `POST /api/v1/notebooks/{id}/quizzes` with `{ "supplement": true }`.

If `SEARXNG_URL` is missing or the instance is down, the response includes a warning and items stay vault-cited.

## S1 shapes (Web)

```ts
type Chat = {
  id: string
  notebook_id: string
  kind: "orchestrator" | "specialist"
  topic_ids: string[]      // empty/broad for orchestrator; 1+ for specialist
  status: "open" | "closed"
  created_at: string
  closed_at: string | null
}

type SpawnOffer = {
  notebook_id: string
  candidates: { topic_id: string; severity: "mild" | "severe"; reason: string }[]
  max_spawn: 2
}

type Handoff = {
  id: string
  from_chat_id: string
  to_chat_id: string       // orchestrator
  topic_ids: string[]
  summary: string
  scoreboard_snapshot: TopicScore[]
  created_at: string
}

type ChatMessage = {
  id: string
  chat_id: string
  role: "user" | "assistant"
  text: string
  created_at: string
}
```

Response wrappers:

- `POST …/chats/specialists` → `{ chat: Chat, warnings: string[] }`
- `POST …/chats/{id}/messages` → `{ message: ChatMessage, quiz?: { quiz, items } }`
- `POST …/chats/{id}/close` → `{ chat: Chat, handoff: Handoff }`

## Tests

```bash
cd packages/study_logic
pip install -e '.[dev]'
pytest
```

S0 gates (still required): confirm, citations, empty vault. S1: offer cap / severe-first, specialist cap, shared scoreboard from specialist attempts, handoff on close.

## Release smoke (S1, same `:8000`)

After S0 confirm → pretest → attempts, on the **same** Backend process:

```bash
# orchestrator get-or-create
curl -fsS -X POST http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK_ID/chats/orchestrator

# offer ≤2, severe-first; mild topics remain on GET …/scoreboard
curl -fsS http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK_ID/spawn-offer

# open ≤2 specialists; a third is 409 TooManySpecialists
curl -fsS -X POST http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK_ID/chats/specialists \
  -H 'Content-Type: application/json' -d '{"topic_ids":["<severe-topic-id>"]}'

# specialist quiz still requires citation_chunk_ids; grade via existing attempts path
curl -fsS -X POST http://127.0.0.1:8000/api/v1/chats/$CHAT_ID/messages \
  -H 'Content-Type: application/json' -d '{"generate_quiz":true}'
curl -fsS -X POST http://127.0.0.1:8000/api/v1/quizzes/$QUIZ_ID/attempts \
  -H 'Content-Type: application/json' -d '{"item_id":"...","selected_choice_id":"..."}'

# close writes a handoff visible on GET handoffs
curl -fsS -X POST http://127.0.0.1:8000/api/v1/chats/$CHAT_ID/close
curl -fsS http://127.0.0.1:8000/api/v1/notebooks/$NOTEBOOK_ID/handoffs
```

Do not require S2 miss→explain→retest. S0 spine (topics, grounded quiz, scoreboard, `install_study_logic`) must stay green.
