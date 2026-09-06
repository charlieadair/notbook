# `@notbook/study-logic`

S0 study engine for Notbook: **topics → grounded pretest → attempts → scoreboard**.

This package is a **library**. It does **not** implement UI, OCR, or an embedding store, and it does **not** own the DEMO ports.

## DEMO composition (production)

| Process | Port | Role |
| --- | --- | --- |
| Web UI | **:3000** | Frontend only |
| Backend **FastAPI** | **:8000** | Single API. Mounts study routes at `/api/v1` |

Production/demo mounts study routes under **Backend FastAPI `/api/v1` on :8000**. This package must not bind `:3000` or `:::3000`. Backend imports `StudyEngine` and wires those handlers. Retrieval stays on Backend (`VaultRetrieve` / StubInference).

```ts
import { StudyEngine, HttpVaultRetrieve, StudyError } from "@notbook/study-logic";

const engine = new StudyEngine({
  vault: new HttpVaultRetrieve("http://127.0.0.1:8000"),
});

// Backend :8000 handlers call:
//   engine.proposeTopics(notebookId)
//   engine.confirmTopics(notebookId, body)
//   engine.listTopics(notebookId)
//   engine.createQuiz(notebookId)
//   engine.gradeAttempt(quizId, body)
//   engine.scoreboard(notebookId)
// Map StudyError.status (409 / 422 / …) onto the HTTP response.
```

## Offline fixture smoke (not DEMO)

`createStudyServer(engine)` + `npm start` is optional, for fixture smoke only. It binds **127.0.0.1** (not all interfaces) on **PORT** (default **3001**).

```bash
npm install
npm test
npm run build
npm start                 # 127.0.0.1:3001 — never :3000 / :::3000
# or: HOST=127.0.0.1 PORT=3001 npm start
bash packages/study-logic/scripts/smoke.sh   # http://127.0.0.1:3001
```

## HTTP routes

All study routes are under `/api/v1` (DEMO: Backend FastAPI `:8000`; offline smoke: `127.0.0.1:3001`).

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/api/v1/notebooks/:id/topics/propose` | Infer topics from vault chunk text. All `confirmed=false`. |
| `POST` | `/api/v1/notebooks/:id/topics/confirm` | Confirm inferred topics, or pass `{ names }` to set an **explicit already-confirmed** list (skips propose). |
| `GET` | `/api/v1/notebooks/:id/topics` | Current topic map. |
| `POST` | `/api/v1/notebooks/:id/quizzes` | Build a `kind: "pretest"` quiz + items. **Not** `/quizzes/pretest`. |
| `POST` | `/api/v1/quizzes/:id/attempts` | Body `{ item_id, selected_choice_id }` → `Attempt` + updated `TopicScore[]`. |
| `GET` | `/api/v1/notebooks/:id/scoreboard` | `{ topics, window: 20, proficiency_bar: 0.8 }`. |

Gates:

- **409 / `TopicsUnconfirmed`** if any topic is missing or unconfirmed.
- **422 / `InsufficientEvidence`** if the vault is empty or has no citable chunks. Items are never invented.

## Confirm rule (SPEC §4/§12)

- **Explicit list up front:** `POST /api/v1/notebooks/:id/topics/confirm` with `{ names: ["Mitosis", ...] }` (or `{ topics }`) writes those topics as **already confirmed**. Skip `propose`.
- **Inferred from materials only:** `propose` (always `confirmed=false`) → `confirm` (no body, or `{ topic_ids }`).

## VaultRetrieve contract (Backend)

Study-logic **consumes** retrieval. Backend implements (do not reimplement the vault here). StubInference on Backend is enough to develop offline.

```
POST /api/v1/notebooks/{notebook_id}/retrieve
  body: { query: string, top_k?: number }   # default top_k = 8
  → { chunks: [{ id, source_id, text, locator, score, source_filename }] }

GET  /api/v1/chunks/{chunk_id}
  → full chunk + source metadata (same fields)
```

```ts
type Chunk = {
  id: string              // citation_chunk_id
  source_id: string
  text: string
  locator: string
  score: number
  source_filename: string // source label
}

interface VaultRetrieve {
  retrieve(args: { notebook_id: string; query: string; top_k?: number }): Promise<Chunk[]>
}
```

- `HttpVaultRetrieve` calls those Backend routes and reads `{ chunks }`. `chunk.id` is written to `QuizItem.citation_chunk_ids`.
- `InMemoryVault` / `createFixtureVault()` are the offline fixture (`notebook_id = nb_bio`). They use the same field names and `{ chunks }` envelope. `getChunk(id)` is the fixture stand-in for `GET /api/v1/chunks/{chunk_id}`.

A chunk is citable only when `id` and `text` are non-empty. Quiz items must have a non-empty `citation_chunk_ids` list pointing at **retrieved** `chunk.id` values. Uncited items are dropped; if nothing remains, the engine returns `InsufficientEvidence`.

## Scoreboard

- Window: **last 20** graded attempts per topic.
- Proficient: `correct_rate >= 0.8`.
- `severity`: `severe` if `rate < 0.5` **or** ≥ 3 misses in the window; `mild` if below proficiency but not severe; `ok` otherwise (including no attempts).

## Module exports

`StudyEngine` is what Backend imports. `createStudyServer(engine)` is a thin Node `http` wrapper for offline smoke only.

## Offline smoke path (port 3001)

```bash
curl -s -X POST http://127.0.0.1:3001/api/v1/notebooks/nb_bio/topics/confirm \
  -H 'content-type: application/json' \
  -d '{"names":["Mitosis","Meiosis"]}'
curl -s -X POST http://127.0.0.1:3001/api/v1/notebooks/nb_bio/quizzes
# DEMO smoke uses Backend :8000 instead of this process.
```
