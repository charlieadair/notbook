# Notbook Web (S0 + S1)

Self-hosted UI for the S0 study loop: **create notebook → upload → inspect vault → confirm topics → pretest → scoreboard**.

S1 (demo bar): after the scoreboard, an **offer** (not auto-spawn) to open at most **2** specialist chats. Orchestrator keeps the holistic map; close a specialist to land a handoff.

This app does **not** invent quiz pedagogy or vault internals. It calls the local Study API (Backend + Study-logic). No auth.

## Stack

Vite + React + TypeScript + React Router. Plain CSS.

## Install and run

```bash
cd web
npm install
cp .env.example .env   # optional; defaults work for local Backend
npm run dev            # http://127.0.0.1:3000
```

```bash
npm test
npm run build
```

## Point at the local Study API

**Web binds `:3000`.** **API is `:8000`.** Default:

`VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`

Study-logic routes (topics, quizzes, attempts, scoreboard) are expected on that **same `/api/v1` base**, mounted behind Backend (or proxied to it). Do **not** point the web app at Study-logic’s standalone Node listener (PR #1 historically used `:3000`) — that port is reserved for this UI.

Same-origin proxy (avoids CORS): `VITE_API_BASE_URL=/api/v1` and `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`.

1. Start Backend on `:8000` (vault + Study-logic under `/api/v1`).
2. `cd web && npm run dev` — listens on `http://127.0.0.1:3000` (`strictPort`).
3. Open that URL — no login.

Health: `GET {VITE_API_BASE_URL}/health`.

Health: the home screen calls `GET {VITE_API_BASE_URL}/health`.

### UI-only mock (API down)

Prefer the real API. If Backend/Study-logic are not running, you can smoke the screens with an in-memory stand-in:

```bash
VITE_USE_MOCK=1 npm run dev
```

This mock is **not** real OCR, retrieval, or grounded generation. Filenames containing `fail` simulate `extract_status: failed`. Do not use it for the judge demo.

## Screens

| Route | Job |
| --- | --- |
| `/` | Create or open a notebook |
| `/notebooks/:id/upload` | File upload + paste; source extract status |
| `/notebooks/:id/vault` | Sources, chunk counts, chunk text |
| `/notebooks/:id/topics` | Propose / edit / confirm; pretest CTA disabled until confirmed |
| `/notebooks/:id/quiz` | One MC item at a time; Show citations → `GET /chunks/:id` |
| `/notebooks/:id/scoreboard` | Per-topic rates, 80% bar, severity; spawn **offer** if Study-logic returns candidates |
| `/notebooks/:id/orchestrator` | Holistic scoreboard + handoffs (S1) |
| `/notebooks/:id/chats/:chatId` | Specialist shell: scoped scores, messages/compose if mounted, **Close & hand off** |

## Empty and error states

- OCR / extract failed on a source (status + re-upload guidance)
- No chunks yet / vault empty
- Topics not confirmed (pretest CTA blocked)
- `409 { error: "topics_unconfirmed" }` on pretest → confirm topics
- `422 { error: "insufficient_evidence" }` → need more materials / weak vault

## Client contract

Typed client in `src/api/`. Base `/api/v1`. Vault names match Backend + OpenAPI on main:

- Ingest: single `POST /notebooks/:id/sources` — multipart `file` or JSON `{ filename?, text }`
- Inspect (vault UI): `GET /notebooks/:id/sources`, `GET /sources/:id/chunks`, `GET /chunks/:id`
- Study: topics propose/confirm/list, `POST /notebooks/:id/quizzes`, `POST /quizzes/:id/attempts`, scoreboard
- S1 (Study-logic PR #24 / issue #22; 404/501 → empty, S0 screens stay up):
  - `GET|POST /notebooks/:id/chats/orchestrator` (idempotent get-or-create)
  - `GET /notebooks/:id/chats` (list; get-or-creates orchestrator)
  - `GET /notebooks/:id/spawn-offer` — empty `candidates` until pretest attempts; never invented client-side
  - `POST /notebooks/:id/chats/specialists` `{ topic_ids }` → `{ chat, warnings[] }` (one chat; 409 `TooManySpecialists` on a third open specialist)
  - `POST /chats/:id/messages` `{ text, generate_quiz? }` → `{ message, quiz? }`
  - `POST /chats/:id/close` → `{ chat, handoff }`
  - `GET /notebooks/:id/handoffs`

Retrieve stays on the client for Study-logic; the vault browser uses inspect only.

Gates: **409** `{ error: "topics_unconfirmed" }`, **422** `{ error: "insufficient_evidence" }`.

Response envelopes are normalized (`[]` or `{ topics }`, `{ quiz, items }`, `{ attempt, scores }` or `{ attempt, scoreboard }`).

Judge click-path: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).
