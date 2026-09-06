# `@notbook/study-logic`

S0 study engine for Notbook: **topics → grounded pretest → attempts → scoreboard**.

This package is the study-logic boundary. It does **not** implement UI, OCR, or an embedding store. Retrieval is injected through `VaultRetrieve` so Backend can own the vault.

## Layout

```
packages/study-logic/
  src/           # engine, HTTP adapter, vault contract, scoring
  tests/         # confirm gate, citations, empty vault, scoreboard, vault contract
```

Root scripts (`npm test`, `npm run build`, `npm start`) delegate here.

## Install / test / run

From the repo root (npm workspaces):

```bash
npm install
npm test
npm run build
npm start          # thin HTTP server on PORT (default 3000)
```

## HTTP routes

S0 sketch paths (exact). The thin server also accepts an `/api/v1` prefix as an alias.

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/notebooks/:id/topics/propose` | Infer topics from vault chunk text. All `confirmed=false`. |
| `POST` | `/notebooks/:id/topics/confirm` | Confirm inferred topics, or pass `{ names }` to set an **explicit already-confirmed** list (skips propose). |
| `GET` | `/notebooks/:id/topics` | Current topic map. |
| `POST` | `/notebooks/:id/quizzes` | Build a `kind: "pretest"` quiz + items. **Not** `/quizzes/pretest`. |
| `POST` | `/quizzes/:id/attempts` | Body `{ item_id, selected_choice_id }` → `Attempt` + updated `TopicScore[]`. |
| `GET` | `/notebooks/:id/scoreboard` | `{ topics, window: 20, proficiency_bar: 0.8 }`. |

Gates:

- **409 / `TopicsUnconfirmed`** if any topic is missing or unconfirmed.
- **422 / `InsufficientEvidence`** if the vault is empty or has no citable chunks. Items are never invented.

## Confirm rule (SPEC §4/§12)

- **Explicit list up front:** `POST /notebooks/:id/topics/confirm` with `{ names: ["Mitosis", ...] }` (or `{ topics }`) writes those topics as **already confirmed**. Skip `propose`.
- **Inferred from materials only:** `propose` (always `confirmed=false`) → `confirm` (no body, or `{ topic_ids }`).

## VaultRetrieve contract (Backend)

Study-logic **consumes** retrieval. Backend implements (do not reimplement the vault here):

```
POST /notebooks/:id/retrieve
  body: { query: string, top_k?: number }
  → Chunk[] or { chunks: Chunk[] }

GET  /chunks/:id
  → Chunk
```

```ts
type Chunk = {
  id: string            // citation_chunk_id
  source_id: string
  text: string
  locator: string
  score: number
  source_filename?: string  // source label
}

interface VaultRetrieve {
  retrieve(args: { notebook_id: string; query: string; top_k?: number }): Promise<Chunk[]>
}
```

- `HttpVaultRetrieve` calls those Backend routes. It accepts a raw chunk array or `{ chunks }`.
- `InMemoryVault` / `createFixtureVault()` are for tests and local smoke only (`notebook_id = nb_bio`). Fixture chunks use the same field names.

A chunk is citable only when `id` and `text` are non-empty. Quiz items must have a non-empty `citation_chunk_ids` list pointing at **retrieved** `chunk.id` values. Uncited items are dropped; if nothing remains, the engine returns `InsufficientEvidence`.

## Scoreboard

- Window: **last 20** graded attempts per topic.
- Proficient: `correct_rate >= 0.8`.
- `severity`: `severe` if `rate < 0.5` **or** ≥ 3 misses in the window; `mild` if below proficiency but not severe; `ok` otherwise (including no attempts).

## Module exports

`StudyEngine` is the main API. `createStudyServer(engine)` is a thin Node `http` wrapper around the same methods.

## Smoke path

With `npm start` and the fixture vault:

```bash
curl -s -X POST http://127.0.0.1:3000/notebooks/nb_bio/topics/propose
curl -s -X POST http://127.0.0.1:3000/notebooks/nb_bio/topics/confirm
curl -s -X POST http://127.0.0.1:3000/notebooks/nb_bio/quizzes
# or skip propose with an explicit list:
curl -s -X POST http://127.0.0.1:3000/notebooks/nb_bio/topics/confirm \
  -H 'content-type: application/json' \
  -d '{"names":["Mitosis","Meiosis"]}'
```
