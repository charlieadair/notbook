# Notbook — Demo (S0)

Release gate for the Student Build Challenge. Contract: [`SPEC.md`](SPEC.md) §12 (S0 acceptance). Self-hosted first. No multi-user auth, no public k8s/Cloudflare ingress, no Legal/ToS for strangers.

**Backend vault is on main** (`backend/`). Study-logic is mounted on the same FastAPI app under `/api/v1`. **Web UI is on main** (`web/`, PR #4). This file pins those run commands. Public GHCR images are for **local** `docker compose` / `docker run` only — not hosted SaaS.

---

## What judges should see (30s story)

Self-hosted study harness; notes stay local; every answer cites what was consumed; scoreboard shows real weaknesses.

In one sitting: upload class materials on your machine → inspect the vault (sources + chunks, not only “upload ok”) → confirm topics → take a grounded pretest → see a per-topic struggle map. If a step needs a cloud login, a public URL, or a ToS click, the demo has failed.

Walk that path in the local UI (`http://127.0.0.1:3000`). The 60s click path is [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md). The curl smoke below is the same beats against `:8000`.

---

## Prerequisites

- **Machine with this repo cloned** (single-user, local) — or just Docker, if you use the published images.
- **Docker** (Compose v2) for the GHCR / compose path.
- **Python 3.11+** for the Study API if you run it from source.
- **Node.js + npm** for the Web UI (`web/`; Vite `npm run dev`) if you run it from source.
- **Tesseract** on the host if you run the API from source and want image/handwriting OCR (`sudo apt-get install tesseract-ocr` on Debian/Ubuntu). The published API image already includes Tesseract. Without it, image ingest still creates a `Source` with `extract_status=failed` — honest failure, not silent success.
- **Inference** — one of:
  - Default **stub** adapter (hash embeddings + fixed JSON complete; no key required).
  - Local model runtime (~16GB GPU VRAM), or
  - BYO / MCP provider you already pay for (OpenAI-compatible).
- **Sample materials** (Backend-owned fixtures on main):
  - [`backend/fixtures/sample.pdf`](backend/fixtures/sample.pdf)
  - [`backend/fixtures/handwritten_scan.png`](backend/fixtures/handwritten_scan.png)

### Env keys (Backend — [`backend/.env.example`](backend/.env.example))

Copy `backend/.env.example` → `backend/.env`. Fill locally; never commit values.

| Key | Intent | Placeholder default |
| --- | --- | --- |
| `DATA_DIR` | Local vault root (`notbook.db` + files). Alias: `NOTBOOK_DATA_DIR` | `data` |
| `INFERENCE_PROVIDER` | `stub` or `openai-compatible`. Alias: `INFERENCE_ADAPTER` | `stub` |
| `OPENAI_API_BASE` | Local runtime or provider endpoint (openai-compatible only) | `http://127.0.0.1:11434/v1` |
| `OPENAI_API_KEY` | Provider key — **never commit** | `sk-not-committed` |
| `EMBED_MODEL` | Embeddings model id. Alias: `OPENAI_EMBED_MODEL` | unset (adapter default) |
| `CHAT_MODEL` | Chat/completions model id. Alias: `OPENAI_CHAT_MODEL` | unset (adapter default) |

Web ([`web/.env.example`](web/.env.example); optional — defaults work for local Backend):

| Key | Intent | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Study API prefix (vault + study-logic) | `http://127.0.0.1:8000/api/v1` |

UI binds **`http://127.0.0.1:3000`** (`npm run dev`, Vite `strictPort`). Do not point `VITE_API_BASE_URL` at Study-logic’s standalone listener, and do not use `VITE_USE_MOCK=1` for the judge path.

Study API base URL is **`http://127.0.0.1:8000`** (not an env pin). Vault, retrieve, and study-logic (topics / quizzes / scoreboard) share that process.

Do **not** put API keys, tokens, or kubeconfigs in the repo or in this file.

---

## Docker (published GHCR images)

Public images — **anonymous `docker pull`, no `docker login`** once GHCR packages are public. Loopback ports only.

Until `docker pull` works anonymously, clone this repo and **build locally** (no GHCR write needed):

```bash
git clone https://github.com/charlieadair/notbook.git
cd notbook
docker compose up --build
curl -fsS http://127.0.0.1:8000/health
# UI: http://127.0.0.1:3000
```

| What | Image |
| --- | --- |
| All-in-one (API + UI) | `ghcr.io/charlieadair/notbook:latest` (also `:s0`) |
| Study API | `ghcr.io/charlieadair/notbook/api:latest` (also `:s0`, `:api` on the repo image) |
| Web UI | `ghcr.io/charlieadair/notbook/web:latest` (also `:s0`, `:web` on the repo image) |

### One container

```bash
docker pull ghcr.io/charlieadair/notbook:latest
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -p 127.0.0.1:3000:3000 \
  -e INFERENCE_PROVIDER=stub \
  ghcr.io/charlieadair/notbook:latest
```

### Compose stack (API + Web)

```bash
git clone https://github.com/charlieadair/notbook.git
cd notbook
docker compose pull
docker compose up
```

`docker compose up --build` builds from this repo instead of pulling.

### Smoke after `up`

```bash
curl -fsS http://127.0.0.1:8000/health
# expect JSON including "status":"ok"
# then open the UI:
#   http://127.0.0.1:3000
```

Compose binds **127.0.0.1** only. A public ingress URL is out of scope. Inference keys, if you use a provider, stay in your shell / local env — never commit them.

Optional BYO inference (host Ollama or any OpenAI-compatible server):

```bash
INFERENCE_PROVIDER=openai-compatible \
OPENAI_API_BASE=http://host.docker.internal:11434/v1 \
OPENAI_API_KEY=sk-local \
docker compose up
```

Images rebuild on `main` via [`.github/workflows/ghcr.yml`](.github/workflows/ghcr.yml).

---

## Install & run (self-hosted, from source)

1. **Clone the repo**

   ```bash
   git clone https://github.com/charlieadair/notbook.git
   cd notbook
   ```

2. **Env file** (optional — stub adapter works with no `.env`)

   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env locally — inference provider + any keys stay on this machine
   ```

3. **Start Study API (Backend)** — vault + study-logic on one FastAPI app:

   ```bash
   cd backend
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e ../packages/study_logic
   pip install -e ".[dev]"
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ./scripts/smoke.sh
   ```

   - Base URL: **http://127.0.0.1:8000**
   - API: http://127.0.0.1:8000/api/v1
   - Health: http://127.0.0.1:8000/health
   - OpenAPI / Swagger: http://127.0.0.1:8000/openapi.json · http://127.0.0.1:8000/docs
   - `packages/study_logic` is mounted under `/api/v1` on this same app (topics, quizzes, scoreboard). There is no second study server.

   Run `./scripts/smoke.sh` from `backend/` with the server already up (Release vault smoke: create notebook → PDF + paste + image → sources → chunks → retrieve).

4. **Start Web UI** (second terminal; Backend already on `:8000`):

   ```bash
   cd web
   npm install
   npm run dev
   # VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1   # default; see web/.env.example
   # UI: http://127.0.0.1:3000
   ```

   - UI: **http://127.0.0.1:3000**
   - Scripts: `dev` (Vite), `build`, `preview`, `test` — see [`web/package.json`](web/package.json)
   - Judge click path: [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md)

5. **Health check**

   ```bash
   curl -fsS http://127.0.0.1:8000/health
   # Then open the UI in a local browser:
   #   http://127.0.0.1:3000
   ```

Both processes must bind **loopback** (or another user-controlled host). A public ingress URL is out of scope and fails the demo.

---

## 60-second judge script

UI-first. Click path (screens, buttons, fail conditions): [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md). Same beats against `:8000` via Swagger or the curl smoke below. Fail the demo if any step requires **cloud multi-user login**, a **public URL**, or **Legal/ToS acceptance**.

1. Open the local UI (`http://127.0.0.1:3000`). No account signup. If the home screen says the API is unreachable, start Backend on `:8000` — do not use `VITE_USE_MOCK=1`.
2. Create or open a notebook. Upload **one PDF** and **one handwritten/scan** image (`backend/fixtures/sample.pdf`, `backend/fixtures/handwritten_scan.png`).
3. Inspect the vault: list sources (filenames + extract/OCR status) and open chunks for each source. Prove **consumption**, not only “upload succeeded.”
4. Confirm proposed topics — or skip propose and use an **explicit topic list** if the UI offers that. Pretest must stay blocked until topics are confirmed (unless the user supplied the list).
5. Start the pretest. On **at least one item**, show citations back to vault chunks (`citation_chunk_ids` → chunk text / locator / source).
6. Submit the quiz. Show the **per-topic scoreboard** update (proficiency bar **80%**; Study-logic window = **last 20 attempts** per topic).

### CLI / API smoke (~60s)

Mirrors the same path against the local Study API on **http://127.0.0.1:8000**. Vault and study-logic share `/api/v1` on that process.

**Vault (Backend)** — `/api/v1`

- `POST /api/v1/notebooks` — `{ "title" }` → notebook `id`
- `POST /api/v1/notebooks/:id/sources` — PDF \| md \| paste \| image/scan (`file=` multipart, or JSON `{filename, text}` for paste)
- `GET /api/v1/notebooks/:id/sources` — list + `extract_status` + `chunk_count`
- `GET /api/v1/sources/:id/chunks` — inspect
- `GET /api/v1/chunks/:id` — text + locator
- `POST /api/v1/notebooks/:id/retrieve` — `{ "query", "top_k" }` → `{ "chunks": [...] }`

**Study-logic (same `:8000`, mounted under `/api/v1`)**

- `POST /api/v1/notebooks/:id/topics/propose`
- `POST /api/v1/notebooks/:id/topics/confirm` — pretest blocked until confirmed (or explicit `{ "names": [...] }` / `{ "topics": [...] }`)
- `GET /api/v1/notebooks/:id/topics`
- `POST /api/v1/notebooks/:id/quizzes` — items **must** have `citation_chunk_ids`; drop/flag low-evidence; **409** `TopicsUnconfirmed` if topics unconfirmed; **422** `InsufficientEvidence` if the vault has no citable chunks
- `POST /api/v1/quizzes/:id/attempts` — `{ "item_id", "selected_choice_id" }` → grade → scoreboard
- `GET /api/v1/notebooks/:id/scoreboard` — `{ "topics", "window": 20, "proficiency_bar": 0.8 }`

Backend retrieve returns `[]` for an empty query, so `topics/propose` (which retrieves with `""`) does not invent names from the vault. The smoke below still asserts **409** before confirm, then uses the SPEC-allowed **explicit topic list** so pretest can retrieve by name.

Official vault-only smoke (server already running): `cd backend && ./scripts/smoke.sh`.

The script below exits **non-zero** if pretest items lack citations or the scoreboard is empty. Requires `curl` and `python3`. Run from the **repo root** with uvicorn on `:8000`.

```bash
#!/usr/bin/env bash
# S0 smoke — ingest → inspect → propose/confirm → pretest → attempt → scoreboard
# One FastAPI process: vault + study_logic under /api/v1 on http://127.0.0.1:8000
set -euo pipefail

API="${NOTBOOK_API_URL:-http://127.0.0.1:8000}"
SMOKE_PDF="${SMOKE_PDF:-./backend/fixtures/sample.pdf}"
SMOKE_SCAN="${SMOKE_SCAN:-./backend/fixtures/handwritten_scan.png}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl_json() {
  local out="$1"; shift
  local code
  code="$(curl -sS -o "$out" -w "%{http_code}" "$@")"
  echo "$code"
}

# 0) Health
curl -fsS "$API/health" >"$tmp/health"

# 1) Create notebook, then ingest PDF + handwritten/scan.
curl -fsS -X POST "$API/api/v1/notebooks" \
  -H "Content-Type: application/json" \
  -d '{"title":"S0 smoke"}' >"$tmp/notebook.json"
NOTEBOOK_ID="$(python3 - "$tmp/notebook.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["id"])
PY
)"

curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/sources" \
  -F "file=@${SMOKE_PDF};type=application/pdf" >"$tmp/src_pdf.json"
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/sources" \
  -F "file=@${SMOKE_SCAN};type=image/png" >"$tmp/src_scan.json"

# 2) List sources + extract status; require at least two sources.
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/sources" >"$tmp/sources.json"
python3 - "$tmp/sources.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
if not isinstance(rows, list) or len(rows) < 2:
    sys.stderr.write("FAIL: expected >=2 sources (PDF + scan) with extract status\n")
    sys.exit(1)
for r in rows:
    if "extract_status" not in r or "chunk_count" not in r:
        sys.stderr.write("FAIL: source missing extract_status/chunk_count\n")
        sys.exit(1)
print("sources", len(rows))
PY

# 3) Inspect chunks for a consumed source; then one chunk body.
SOURCE_ID="$(python3 - "$tmp/sources.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
print(next(r["id"] for r in rows if r.get("chunk_count", 0) > 0))
PY
)"
curl -fsS "$API/api/v1/sources/${SOURCE_ID}/chunks" >"$tmp/chunks.json"
CHUNK_ID="$(python3 - "$tmp/chunks.json" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))
if not rows:
    sys.stderr.write("FAIL: no chunks — upload-ok without consumption\n")
    sys.exit(1)
print(rows[0]["id"])
PY
)"
curl -fsS "$API/api/v1/chunks/${CHUNK_ID}" >"$tmp/chunk.json"
python3 - "$tmp/chunk.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
if not str(c.get("text") or "").strip():
    sys.stderr.write("FAIL: chunk has no text/locator payload\n")
    sys.exit(1)
print("chunk_ok", c["id"])
PY

# Retrieve — citable chunks for a query (Backend path).
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/retrieve" \
  -H "Content-Type: application/json" \
  -d '{"query":"spectral theorem","top_k":8}' >"$tmp/retrieve.json"
python3 - "$tmp/retrieve.json" <<'PY'
import json, sys
hits = json.load(open(sys.argv[1])).get("chunks") or []
if not hits:
    sys.stderr.write("FAIL: retrieve returned no citable chunks\n")
    sys.exit(1)
print("retrieve", len(hits))
PY

# 4–6) Study routes on the same :8000 /api/v1 app (topics / quizzes / scoreboard).
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/topics/propose" \
  -H "Content-Type: application/json" \
  -d '{}' >"$tmp/propose.json"

pre_code="$(curl_json "$tmp/pretest_blocked.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API/api/v1/notebooks/${NOTEBOOK_ID}/quizzes")"
if [[ "$pre_code" != "409" ]]; then
  echo "FAIL: pretest before confirm must be 409 (got ${pre_code})" >&2
  exit 1
fi

# Confirm an explicit topic list (no forced re-propose). Empty-body confirm
# of a [] propose stays unconfirmed — Backend retrieve("") is [].
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/topics/confirm" \
  -H "Content-Type: application/json" \
  -d '{"names":["spectral theorem"]}' >"$tmp/confirm.json"
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/topics" >"$tmp/topics.json"

# 5) Pretest — items MUST include citation_chunk_ids; 422 if evidence is thin.
pre_code="$(curl_json "$tmp/pretest.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API/api/v1/notebooks/${NOTEBOOK_ID}/quizzes")"
if [[ "$pre_code" == "422" ]]; then
  echo "FAIL: 422 insufficient evidence — do not invent items; fix vault/retrieve" >&2
  exit 1
fi
if [[ "$pre_code" != "200" && "$pre_code" != "201" ]]; then
  echo "FAIL: pretest HTTP ${pre_code}" >&2
  exit 1
fi

QUIZ_ID="$(python3 - "$tmp/pretest.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
q = payload.get("quiz") or payload
items = payload.get("items") or q.get("items") or q.get("questions") or []
if not items:
    sys.stderr.write("FAIL: pretest returned no items\n")
    sys.exit(1)
missing = []
for i, item in enumerate(items):
    cites = item.get("citation_chunk_ids")
    if not isinstance(cites, list) or len(cites) == 0:
        missing.append(item.get("id") or i)
if missing:
    sys.stderr.write(f"FAIL: items missing citation_chunk_ids: {missing}\n")
    sys.exit(1)
print(q.get("id") or payload.get("id") or "")
if not (q.get("id") or payload.get("id")):
    sys.stderr.write("FAIL: pretest response has no quiz id\n")
    sys.exit(1)
PY
)"

# 6) Grade one attempt, then read scoreboard.
ITEM_ID="$(python3 - "$tmp/pretest.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
items = payload.get("items") or payload.get("questions") or []
print(items[0]["id"])
PY
)"
CHOICE_ID="$(python3 - "$tmp/pretest.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
items = payload.get("items") or payload.get("questions") or []
choices = items[0].get("choices") or []
print((choices[0] or {}).get("id") or items[0].get("correct_choice_id") or "")
PY
)"
curl -fsS -X POST "$API/api/v1/quizzes/${QUIZ_ID}/attempts" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\": \"${ITEM_ID}\", \"selected_choice_id\": \"${CHOICE_ID}\"}" >"$tmp/attempt.json"

curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/scoreboard" >"$tmp/scoreboard.json"
python3 - "$tmp/scoreboard.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else (
    data.get("topics") or data.get("scoreboard") or data.get("items") or []
)
if not rows:
    sys.stderr.write("FAIL: empty scoreboard after attempt\n")
    sys.exit(1)
print("scoreboard_topics", len(rows))
PY

echo "S0 API smoke: ingest → inspect → confirm → cited pretest → scoreboard OK"
```

---

## Release smoke checklist (“demo green”)

Release runs this on a **fresh shell** before calling the demo green. Maps to [`SPEC.md`](SPEC.md) §12 S0 acceptance.

- [ ] API starts cleanly from DEMO install steps on a fresh shell (`backend/` → uvicorn `:8000`)
- [ ] `cd backend && ./scripts/smoke.sh` passes (vault: notebooks / sources / chunks / retrieve)
- [ ] Upload PDF + handwritten/scan both appear as searchable vault content
- [ ] Sources list + chunk inspect work (not only upload succeeded)
- [ ] Study routes (topics / quizzes / scoreboard) answer on the same `:8000` `/api/v1` app
- [ ] Without explicit topics: propose waits for confirm before pretest
- [ ] With explicit topics: pretest uses them without forced re-propose
- [ ] Quiz items include `citation_chunk_ids`; low-evidence not silently invented
- [ ] Completing pretest updates visible per-topic scoreboard
- [ ] Demo narrative holds: local materials, visible consumption, grounded quiz
- [ ] No secrets in git; no multi-user auth / public ingress / Legal docs required for the path
- [ ] Web UI starts from DEMO install steps (`cd web && npm install && npm run dev` → `http://127.0.0.1:3000`)
- [ ] 60s judge click path in [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md) completes against the real `:8000` API (no mock)
- [ ] Home screen shows API connected (not “API unreachable”)
- [ ] `docker pull ghcr.io/charlieadair/notbook:latest` works anonymously; compose `/health` + UI load

Backend + Web install on main. Study-logic is on the `:8000` app. Judge path is local UI `:3000` + API `:8000`. Docker/GHCR is the Release publish path (issue #7) — local pull/run only.

---

## Out of scope (will block merge if required for challenge)

These are S4 / later. A PR that makes any of them **required** for the judge path does not merge:

- Multi-user auth
- Privacy Policy / ToS for strangers
- Public k8s / Cloudflare ingress (a **local** GHCR image for `docker compose` / `docker run` is in-scope; hosted SaaS is not)
- S2 miss→explain→retest polish (S1 chat-tree API is open on the same `:8000` `/api/v1` router; Web UI for chats is separate)

Notbook S0 is a local study harness, not a hosted product.
