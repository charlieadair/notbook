# `@notbook/study-logic`

S0 study engine for Notbook: **topics → grounded pretest → attempts → scoreboard**.

This package is the study-logic boundary. It does **not** implement UI, OCR, or an embedding store. Retrieval is injected through `VaultRetrieve` so Backend can own the vault.

## Layout

```
packages/study-logic/
  src/           # engine, HTTP adapter, vault contract, scoring
  tests/         # confirm gate, citations, empty vault, scoreboard
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

Or from this directory:

```bash
npm install
npm test
npm run build
npm start
```

## HTTP routes

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/notebooks/:id/topics/propose` | Infer topics from vault chunk text. All `confirmed=false`. |
| `POST` | `/notebooks/:id/topics/confirm` | Confirm inferred topics, or pass `{ names }` to set an **explicit already-confirmed** list (skips propose). |
| `GET` | `/notebooks/:id/topics` | Current topic map. |
| `POST` | `/notebooks/:id/quizzes` | Build a `kind: "pretest"` quiz + items. |
| `POST` | `/quizzes/:id/attempts` | Body `{ item_id, selected_choice_id }` → `Attempt` + updated `TopicScore[]`. |
| `GET` | `/notebooks/:id/scoreboard` | `{ topics, window: 20, proficiency_bar: 0.8 }`. |

Gates:

- **409 / `TopicsUnconfirmed`** if any topic is missing or unconfirmed.
- **422 / `InsufficientEvidence`** if the vault is empty or has no citable chunks. Items are never invented.

## Confirm rule

- Inferred path: `propose` (unconfirmed) → `confirm` (sets `confirmed=true`).
- Explicit path: `confirm` with `{ names: ["Mitosis", ...] }` writes those topics as **already confirmed**. Do not require propose first.

## VaultRetrieve contract (Backend)

Study-logic **consumes** retrieval. Backend implements:

```
POST /notebooks/:id/retrieve   { query, top_k? }  → Chunk[]  (or { chunks: Chunk[] })
GET  /chunks/:id                                  → Chunk
```

```ts
type Chunk = { id: string; text: string; source_id?: string; source_label?: string }

interface VaultRetrieve {
  retrieve(args: { notebook_id: string; query: string; top_k?: number }): Promise<Chunk[]>
}
```

- `HttpVaultRetrieve` calls those Backend routes.
- `InMemoryVault` / `createFixtureVault()` are for tests and local smoke only (`notebook_id = nb_bio`).

A chunk is citable only when `id` and `text` are non-empty. Quiz items must have a non-empty `citation_chunk_ids` list pointing at **retrieved** chunk ids. Uncited items are dropped; if nothing remains, the engine returns `InsufficientEvidence`.

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
