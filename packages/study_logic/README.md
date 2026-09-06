# `study-logic` (Python / FastAPI)

S0 + S1 study engine mount for DEMO: **one FastAPI process on :8000**. Backend includes this router (`install_study_logic` / `create_router`). There is no second Node server and no proxy.

The TypeScript package in `packages/study-logic` remains as reference/tests. **DEMO must use this FastAPI router.** S2 (miss→explain→retest) is out.

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
| `POST` | `/api/v1/chats/{id}/messages` — `{ "role"?, "text"?, "generate_quiz"? }` |
| `POST` | `/api/v1/chats/{id}/close` — specialist → orchestrator handoff |
| `GET` | `/api/v1/notebooks/{id}/handoffs` |

- **409 `TopicsUnconfirmed`** until the topic map is confirmed.
- **422 `InsufficientEvidence`** if retrieve returns no citable chunks — never invent items.
- **409 `TooManySpecialists`** if a third open specialist would be created (`max_spawn` = **2**).
- **409 `ChatClosed`** if posting to a closed chat.
- Explicit `{ "names": [...] }` on confirm writes already-confirmed topics (skip propose).
- Every quiz item has `citation_chunk_ids` = retrieved `chunk.id` (including `generate_quiz` on a chat).
- Scoreboard: last **20** attempts / topic, proficiency **0.8**. Shared by orchestrator and specialists — grade via `POST /quizzes/{id}/attempts`.
- Spawn offer is **after pretest scores**, **severe-first**, **≤ 2** candidates. Mild gaps stay on the scoreboard (not hidden). Topics not in the offer may still be opened (soft `warnings[]`).
- Close writes an auto **Handoff** into the orchestrator with a progress summary + `scoreboard_snapshot`. Summary is scoreboard/progress only (no unsourced teaching claims).

Optional `{ "topic_ids": [...] }` on `POST /quizzes` scopes generation; omit it for the S0 whole-notebook pretest.

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
