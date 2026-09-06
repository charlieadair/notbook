# Notbook Web (S0)

Self-hosted UI for the S0 study loop: **create notebook → upload → inspect vault → confirm topics → pretest → scoreboard**.

This app does **not** invent quiz pedagogy or vault internals. It calls the local Study API (Backend + Study-logic). No auth.

## Stack

Vite + React + TypeScript + React Router. Plain CSS.

## Install and run

```bash
cd web
npm install
cp .env.example .env   # optional; defaults work for local Backend
npm run dev            # http://127.0.0.1:5173
```

```bash
npm test
npm run build
```

## Point at the local Study API

Set `VITE_API_BASE_URL` to the API prefix the servers actually serve.

| Setup | Example |
| --- | --- |
| Backend with `/api/v1` (default) | `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` |
| Study-logic HTTP wrapper alone (PR #1, no prefix) | `VITE_API_BASE_URL=http://127.0.0.1:3000` |
| Same-origin via Vite proxy (avoids CORS) | `VITE_API_BASE_URL=/api/v1` and `VITE_API_PROXY_TARGET=http://127.0.0.1:8000` |

The client always appends paths such as `/notebooks`, `/health`, `/chunks/:id`. Include `/api/v1` in the base URL when Backend mounts there.

Vault routes match Backend PR #3 OpenAPI (`GET/POST /api/v1/notebooks`, upload/paste, sources, chunks, retrieve, `{status:"ok"}` health). Study routes match Study-logic PR #1.

1. Start Backend (vault + ingest) on the host/port it documents — expected default `http://127.0.0.1:8000`.
2. Start Study-logic if it is a separate process, or use the combined Study API if Backend fronts those routes.
3. `cd web && npm run dev`
4. Open `http://127.0.0.1:5173` — no login.

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
| `/notebooks/:id/scoreboard` | Per-topic rates, 80% bar, severity |

## Empty and error states

- OCR / extract failed on a source (status + re-upload guidance)
- No chunks yet / vault empty
- Topics not confirmed (pretest CTA blocked)
- `409 TopicsUnconfirmed` on pretest → confirm topics
- `422 InsufficientEvidence` → need more materials / weak vault

## Client contract

Typed client in `src/api/`. Paths match the S0 sketch and Study-logic PR #1:

- Vault: `POST/GET /notebooks`, upload, paste, sources, chunks, `GET /chunks/:id`, retrieve, health
- Study: topics propose/confirm/list, **`POST /notebooks/:id/quizzes/pretest`** with fallback to `POST /notebooks/:id/quizzes` on 404, attempts, scoreboard

Response envelopes are normalized (`[]` or `{ topics }`, `{ quiz, items }`, etc.).

Judge click-path: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).
