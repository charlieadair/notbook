# Notbook — Demo (S0 + S1)

Release gate for the Student Build Challenge. Contract: [`SPEC.md`](SPEC.md) §12 (S0 acceptance) plus the S1 chat-tree (spawn offer → specialist → handoff). Self-hosted first. No multi-user auth, no public k8s/Cloudflare ingress, no Legal/ToS for strangers.

**S0 is the primary path.** S1 is the extension after scoreboard: worst topic does not hijack forever; mild gaps stay visible. **Backend vault is on main** (`backend/`). Study-logic (S0 + S1) is mounted on the same FastAPI app under `/api/v1`. **Web UI is on main** (`web/`, PRs #4 / #25). This file pins those run commands. Public GHCR images are for **local** `docker compose` / `docker run` only — not hosted SaaS.

---

## What judges should see (30s story)

Self-hosted study harness; notes stay local; every answer cites what was consumed; scoreboard shows real weaknesses.

In one sitting: upload class materials on your machine → inspect the vault (sources + chunks, not only “upload ok”) → confirm topics → take a grounded pretest → see a per-topic struggle map → (S1) accept a **spawn offer** for the worst gaps, close a specialist, and still see mild gaps on the scoreboard. If a step needs a cloud login, a public URL, or a ToS click, the demo has failed.

Walk that path in the local UI (`http://127.0.0.1:3000`). The 60–90s click path is [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md). The curl smoke below is the same beats against `:8000`.

---

## Prerequisites

- **Machine with this repo cloned** (single-user, local) — or just Docker, if you use the published images.
- **Docker** (Compose v2) for the GHCR / compose path.
- **Python 3.11+** for the Study API if you run it from source.
- **Node.js + npm** for the Web UI (`web/`; Vite `npm run dev`) if you run it from source.
- **Tesseract** on the host if you run the API from source and want image/handwriting OCR (`brew install tesseract` on macOS; `sudo apt-get install tesseract-ocr` on Debian/Ubuntu). The published GHCR API image already bakes Tesseract (Release owns the image). Without it, image ingest still creates a `Source` with `extract_status=failed` — honest failure, not silent success.
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
| `SEARXNG_URL` | Optional. Study-logic SearXNG client for `supplement=true` quizzes. Unset → vault-only. **Not on the judge path.** | unset |

Web ([`web/.env.example`](web/.env.example); optional — defaults work for local Backend):

| Key | Intent | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Study API prefix (vault + study-logic) | `http://127.0.0.1:8000/api/v1` |

UI binds **`http://127.0.0.1:3000`** (`npm run dev`, Vite `strictPort`). Do not point `VITE_API_BASE_URL` at Study-logic’s standalone listener, and do not use `VITE_USE_MOCK=1` for the judge path.

Study API base URL is **`http://127.0.0.1:8000`** (not an env pin). Vault, retrieve, and study-logic (topics / quizzes / scoreboard) share that process.

Do **not** put API keys, tokens, or kubeconfigs in the repo or in this file.

---

## Docker (published GHCR images)

Public images — **anonymous `docker pull`, no `docker login`** once GHCR packages are public. Loopback ports only. Images are **multi-arch** (`linux/amd64` and `linux/arm64`); Apple Silicon Macs can pull and run without `--platform linux/amd64`.

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
   - `packages/study_logic` is mounted under `/api/v1` on this same app (topics, quizzes, scoreboard, S1 chats). There is no second study server.

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

S0 steps 1–6 are the primary path and must stay green. **S1** (spawn offer → specialist → handoff) is the extension below — same sitting, about +30s. UI clicks: [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md).

### CLI / API smoke (~60s)

Mirrors the same path against the local Study API on **http://127.0.0.1:8000**. Vault and study-logic share `/api/v1` on that process.

**Vault (Backend)** — `/api/v1`

- `POST /api/v1/notebooks` — `{ "title" }` → notebook `id`
- `POST /api/v1/notebooks/:id/sources` — PDF \| md \| paste \| image/scan (`file=` multipart, or JSON `{filename, text}` for paste)
- `GET /api/v1/notebooks/:id/sources` — list + `extract_status` + `chunk_count`
- `GET /api/v1/notebooks/:id/chunks?limit=32` — recent/representative chunks for topic propose (no scores; empty notebook → `[]`)
- `GET /api/v1/sources/:id/chunks` — inspect
- `GET /api/v1/chunks/:id` — text + locator
- `POST /api/v1/notebooks/:id/retrieve` — `{ "query", "top_k" }` → `{ "chunks": [...] }` (blank/whitespace query → `{chunks:[]}`)

**Study-logic (same `:8000`, mounted under `/api/v1`)**

- `POST /api/v1/notebooks/:id/topics/propose`
- `POST /api/v1/notebooks/:id/topics/confirm` — pretest blocked until confirmed (or explicit `{ "names": [...] }` / `{ "topics": [...] }`)
- `GET /api/v1/notebooks/:id/topics`
- `POST /api/v1/notebooks/:id/quizzes` — items **must** have `citation_chunk_ids`; drop/flag low-evidence; **409** `TopicsUnconfirmed` if topics unconfirmed; **422** `InsufficientEvidence` if the vault has no citable chunks
- `POST /api/v1/quizzes/:id/attempts` — `{ "item_id", "selected_choice_id" }` → grade → scoreboard
- `GET /api/v1/notebooks/:id/scoreboard` — `{ "topics", "window": 20, "proficiency_bar": 0.8 }`
- S1 (same router; on main): `GET|POST …/chats/orchestrator`, `GET …/spawn-offer`, `POST …/chats/specialists`, `POST /api/v1/chats/:id/messages` (`text` or `content` alias), `POST /api/v1/chats/:id/close`, `GET …/handoffs` — see [S1 extension](#s1-extension-spawn-offer--handoff-30s)

`topics/propose` samples vault chunks (`GET /api/v1/notebooks/:id/chunks?limit=32` or the in-process `list_chunks` callable) and never calls retrieve with `query=""`. Empty vault → `[]`. The smoke below still asserts **409** before confirm, then uses the SPEC-allowed **explicit topic list** so pretest can retrieve by name.

Official vault-only smoke (server already running): `cd backend && ./scripts/smoke.sh`.

The script below exits **non-zero** if pretest items lack citations or the scoreboard is empty. An optional **S1 block** at the end of the same script asserts spawn-offer / specialist / handoff (exits non-zero on fail). Requires `curl` and `python3`. Run from the **repo root** with uvicorn on `:8000`.

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

# Confirm an explicit topic list (no forced re-propose). After ingest,
# propose may return draft names from sampled chunks; explicit names still win.
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

# ---------------------------------------------------------------------------
# S1 extension (optional) — same $NOTEBOOK_ID / $tmp. ADHD win: worst topic
# does not hijack forever; mild gaps stay on the scoreboard.
# Default on (S1 is on main). If spawn-offer is 404/501: S0 already passed;
# set NOTBOOK_SMOKE_S1=0 to skip, or leave default 1 to fail closed.
# ---------------------------------------------------------------------------
S1="${NOTBOOK_SMOKE_S1:-1}"
if [[ "$S1" != "1" ]]; then
  echo "S1 smoke skipped (NOTBOOK_SMOKE_S1=${S1}). S0 smoke already passed."
  exit 0
fi
s1_code="$(curl_json "$tmp/s1_probe.json" "$API/api/v1/notebooks/${NOTEBOOK_ID}/spawn-offer")"
if [[ "$s1_code" == "404" || "$s1_code" == "501" ]]; then
  echo "S1 routes not mounted (HTTP ${s1_code}). S0 smoke already passed."
  echo "FAIL: S1 spawn-offer expected on main (set NOTBOOK_SMOKE_S1=0 to skip)" >&2
  exit 1
fi
if [[ "$s1_code" != "200" ]]; then
  echo "FAIL: GET spawn-offer HTTP ${s1_code}" >&2
  exit 1
fi

# Extra paste so the second topic name retrieves distinct citable sentences.
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/sources" \
  -H "Content-Type: application/json" \
  -d '{"filename":"s1-mild.md","text":"A real symmetric matrix is orthogonally diagonalizable. Inner products induce norms on the space. Cauchy-Schwarz holds in every inner product space."}' \
  >"$tmp/s1_paste.json"

# Two explicit topics so the scoreboard can show severe + mild. New topic ids
# mean S0's attempt no longer matches — spawn-offer is empty before this pretest.
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/topics/confirm" \
  -H "Content-Type: application/json" \
  -d '{"names":["spectral theorem","symmetric matrix"]}' >"$tmp/s1_confirm.json"

# Orchestrator is get-or-create (no extra CTA).
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/chats/orchestrator" \
  >"$tmp/s1_orch.json"

# Empty before attempts.
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/spawn-offer" >"$tmp/s1_offer_empty.json"
python3 - "$tmp/s1_offer_empty.json" <<'PY'
import json, sys
offer = json.load(open(sys.argv[1]))
cands = offer.get("candidates") or []
if cands:
    sys.stderr.write("FAIL: spawn-offer must be empty before attempts\n")
    sys.exit(1)
if int(offer.get("max_spawn") or 0) != 2:
    sys.stderr.write(f"FAIL: max_spawn must be 2 (got {offer.get('max_spawn')})\n")
    sys.exit(1)
print("spawn_offer_empty_ok")
PY

# S1 pretest — grade one topic all-wrong (severe) and another 1/2 (mild).
s1_quiz_code="$(curl_json "$tmp/s1_pretest.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API/api/v1/notebooks/${NOTEBOOK_ID}/quizzes")"
if [[ "$s1_quiz_code" == "422" ]]; then
  echo "FAIL: S1 pretest 422 insufficient evidence" >&2
  exit 1
fi
if [[ "$s1_quiz_code" != "200" && "$s1_quiz_code" != "201" ]]; then
  echo "FAIL: S1 pretest HTTP ${s1_quiz_code}" >&2
  exit 1
fi

python3 - "$tmp/s1_pretest.json" "$tmp/s1_grades.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
quiz = payload.get("quiz") or payload
items = payload.get("items") or quiz.get("items") or quiz.get("questions") or []
if not items:
    sys.stderr.write("FAIL: S1 pretest returned no items\n")
    sys.exit(1)
by_topic = {}
for item in items:
    tid = (item.get("topic_ids") or [""])[0]
    by_topic.setdefault(tid, []).append(item)
topic_ids = list(by_topic)
severe_tid = topic_ids[0]
mild_tid = topic_ids[1] if len(topic_ids) > 1 else topic_ids[0]
grades = []
for tid, rows in by_topic.items():
    for i, item in enumerate(rows):
        choices = item.get("choices") or []
        correct = item.get("correct_choice_id") or ""
        wrong = next((c.get("id") for c in choices if c.get("id") and c.get("id") != correct), "")
        # Severe topic: miss every item. Mild topic: first correct, rest wrong → 1/2.
        if tid == severe_tid and tid != mild_tid:
            pick = wrong or correct
        elif tid == mild_tid and i == 0:
            pick = correct
        else:
            pick = wrong or correct
        grades.append({"item_id": item["id"], "selected_choice_id": pick, "quiz_id": quiz.get("id") or payload.get("id")})
json.dump({"severe": severe_tid, "mild": mild_tid, "quiz_id": quiz.get("id") or payload.get("id"), "grades": grades}, open(sys.argv[2], "w"))
print("s1_items", len(items), "topics", len(topic_ids))
PY

S1_QUIZ_ID="$(python3 -c 'import json; print(json.load(open("'"$tmp"'/s1_grades.json"))["quiz_id"])')"
python3 - "$tmp/s1_grades.json" "$API" "$S1_QUIZ_ID" <<'PY'
import json, sys, urllib.request
plan = json.load(open(sys.argv[1]))
api, quiz_id = sys.argv[2], sys.argv[3]
for row in plan["grades"]:
    req = urllib.request.Request(
        f"{api}/api/v1/quizzes/{quiz_id}/attempts",
        data=json.dumps({"item_id": row["item_id"], "selected_choice_id": row["selected_choice_id"]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            sys.stderr.write(f"FAIL: S1 attempt HTTP {resp.status}\n")
            sys.exit(1)
print("s1_attempts", len(plan["grades"]))
PY

# If the first quiz only produced one item on the mild topic, add a miss so 1/2 = mild.
python3 - "$tmp/s1_grades.json" "$API" "$NOTEBOOK_ID" "$tmp" <<'PY'
import json, sys, urllib.request

plan = json.load(open(sys.argv[1]))
api, notebook_id, tmp = sys.argv[2], sys.argv[3], sys.argv[4]
mild, severe = plan["mild"], plan["severe"]

def get(path):
    with urllib.request.urlopen(f"{api}{path}") as resp:
        return json.load(resp)

def post(path, body):
    req = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)

def board_rows():
    data = get(f"/api/v1/notebooks/{notebook_id}/scoreboard")
    return data if isinstance(data, list) else (data.get("topics") or [])

rows = {r["topic_id"]: r for r in board_rows()}
need_mild = rows.get(mild, {}).get("severity") != "mild" or mild == severe
if need_mild and mild:
    quiz = post(f"/api/v1/notebooks/{notebook_id}/quizzes", {"topic_ids": [mild]})
    items = quiz.get("items") or (quiz.get("quiz") or {}).get("items") or []
    quiz_id = (quiz.get("quiz") or quiz).get("id")
    if items and quiz_id:
        item = items[0]
        correct = item.get("correct_choice_id") or ""
        wrong = next((c.get("id") for c in (item.get("choices") or []) if c.get("id") != correct), correct)
        # Drive toward 1/2: if currently all-correct, miss; else mark correct.
        pick = wrong if (rows.get(mild, {}).get("correct_rate") or 0) >= 0.8 else (correct or wrong)
        post(f"/api/v1/quizzes/{quiz_id}/attempts", {"item_id": item["id"], "selected_choice_id": pick})
print("scoreboard_seeded")
PY

# After pretest — ≤2, severe-first.
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/spawn-offer" >"$tmp/s1_offer.json"
python3 - "$tmp/s1_offer.json" "$tmp/s1_pick.json" <<'PY'
import json, sys
offer = json.load(open(sys.argv[1]))
cands = offer.get("candidates") or []
if len(cands) == 0:
    sys.stderr.write("FAIL: spawn-offer empty after pretest attempts\n")
    sys.exit(1)
if len(cands) > 2:
    sys.stderr.write(f"FAIL: spawn-offer returned {len(cands)} candidates (max 2)\n")
    sys.exit(1)
if int(offer.get("max_spawn") or 0) != 2:
    sys.stderr.write("FAIL: max_spawn must be 2\n")
    sys.exit(1)
severities = [c.get("severity") for c in cands]
if "mild" in severities and "severe" in severities and severities[0] != "severe":
    sys.stderr.write("FAIL: spawn-offer must be severe-first\n")
    sys.exit(1)
# Prefer a severe candidate when present.
pick = next((c["topic_id"] for c in cands if c.get("severity") == "severe"), cands[0]["topic_id"])
json.dump({"topic_id": pick}, open(sys.argv[2], "w"))
print("spawn_offer", len(cands), "severe_first", severities)
PY

# Shared scoreboard — mild stays listed (neglect-aware), not hidden by the offer.
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/scoreboard" >"$tmp/s1_scoreboard.json"
python3 - "$tmp/s1_scoreboard.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else (data.get("topics") or data.get("scoreboard") or [])
if not rows:
    sys.stderr.write("FAIL: empty S1 scoreboard\n")
    sys.exit(1)
sevs = {r.get("severity") for r in rows}
gaps = [r for r in rows if r.get("severity") in ("mild", "severe")]
if not gaps:
    sys.stderr.write("FAIL: scoreboard has no mild/severe gaps after S1 pretest\n")
    sys.exit(1)
if "mild" not in sevs:
    sys.stderr.write("FAIL: mild gap missing on scoreboard (neglect-aware)\n")
    sys.exit(1)
print("scoreboard_gaps", sorted(sevs))
PY

TOPIC_ID="$(python3 -c 'import json; print(json.load(open("'"$tmp"'/s1_pick.json"))["topic_id"])')"
curl -fsS -X POST "$API/api/v1/notebooks/${NOTEBOOK_ID}/chats/specialists" \
  -H "Content-Type: application/json" \
  -d "{\"topic_ids\":[\"${TOPIC_ID}\"]}" >"$tmp/s1_specialist.json"
SPEC="$(python3 - "$tmp/s1_specialist.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
chat = payload.get("chat") or payload
if not chat.get("id"):
    sys.stderr.write("FAIL: specialists POST missing chat.id\n")
    sys.exit(1)
if chat.get("kind") not in (None, "specialist"):
    sys.stderr.write("FAIL: expected specialist chat\n")
    sys.exit(1)
print(chat["id"])
PY
)"

# Work the specialist — `content` alias (#31); optional generate_quiz still cited.
curl -fsS -X POST "$API/api/v1/chats/${SPEC}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Stay on this topic."}' >"$tmp/s1_msg.json"
gen_code="$(curl_json "$tmp/s1_gen.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{"generate_quiz":true}' \
  "$API/api/v1/chats/${SPEC}/messages")"
if [[ "$gen_code" != "200" && "$gen_code" != "201" ]]; then
  echo "FAIL: specialist generate_quiz HTTP ${gen_code}" >&2
  exit 1
fi
python3 - "$tmp/s1_gen.json" "$API" <<'PY'
import json, sys, urllib.request
payload = json.load(open(sys.argv[1]))
quiz = payload.get("quiz") or {}
items = quiz.get("items") or []
if not items:
    sys.stderr.write("FAIL: generate_quiz returned no items\n")
    sys.exit(1)
missing = [item.get("id") for item in items if not (item.get("citation_chunk_ids") or [])]
if missing:
    sys.stderr.write(f"FAIL: specialist quiz items missing citations: {missing}\n")
    sys.exit(1)
item = items[0]
qid = (quiz.get("quiz") or quiz).get("id")
if qid:
    req = urllib.request.Request(
        f"{sys.argv[2]}/api/v1/quizzes/{qid}/attempts",
        data=json.dumps({"item_id": item["id"], "selected_choice_id": item.get("correct_choice_id") or (item.get("choices") or [{}])[0].get("id")}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req).read()
print("specialist_quiz_cited", len(items))
PY

# Mild still listed after specialist work.
curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/scoreboard" >"$tmp/s1_scoreboard_after.json"
python3 - "$tmp/s1_scoreboard_after.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else (data.get("topics") or [])
if not any(r.get("severity") == "mild" for r in rows):
    sys.stderr.write("FAIL: mild gap vanished after specialist work\n")
    sys.exit(1)
print("mild_still_listed")
PY

curl -fsS -X POST "$API/api/v1/chats/${SPEC}/close" >"$tmp/s1_close.json"
python3 - "$tmp/s1_close.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
handoff = payload.get("handoff") or payload
chat = payload.get("chat") or {}
if chat.get("status") not in (None, "closed"):
    sys.stderr.write("FAIL: close did not mark specialist closed\n")
    sys.exit(1)
if not str(handoff.get("summary") or "").strip():
    sys.stderr.write("FAIL: handoff missing summary\n")
    sys.exit(1)
snap = handoff.get("scoreboard_snapshot")
if not isinstance(snap, list) or not snap:
    sys.stderr.write("FAIL: handoff missing scoreboard_snapshot\n")
    sys.exit(1)
print("handoff_ok", handoff.get("id"))
PY

curl -fsS "$API/api/v1/notebooks/${NOTEBOOK_ID}/handoffs" >"$tmp/s1_handoffs.json"
python3 - "$tmp/s1_close.json" "$tmp/s1_handoffs.json" "$tmp/s1_scoreboard_after.json" <<'PY'
import json, sys
closed = json.load(open(sys.argv[1]))
listed = json.load(open(sys.argv[2]))
board = json.load(open(sys.argv[3]))
handoff = closed.get("handoff") or closed
rows = listed if isinstance(listed, list) else (listed.get("handoffs") or [])
ids = {r.get("id") for r in rows}
if handoff.get("id") not in ids:
    sys.stderr.write("FAIL: GET handoffs missing the closed specialist handoff\n")
    sys.exit(1)
landed = next(r for r in rows if r.get("id") == handoff.get("id"))
if not str(landed.get("summary") or "").strip():
    sys.stderr.write("FAIL: listed handoff missing summary\n")
    sys.exit(1)
if not isinstance(landed.get("scoreboard_snapshot"), list):
    sys.stderr.write("FAIL: listed handoff missing scoreboard_snapshot\n")
    sys.exit(1)
topics = board if isinstance(board, list) else (board.get("topics") or [])
if not any(r.get("severity") == "mild" for r in topics):
    sys.stderr.write("FAIL: mild/stale topic missing on scoreboard after handoff\n")
    sys.exit(1)
print("handoffs", len(rows))
PY

echo "S1 API smoke: empty offer → severe-first spawn → specialist → handoff; mild still listed OK"
```

UI clicks for the same beats: [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md) (S0 steps 1–6, then S1 steps 7–13).

---

## S1 extension (spawn offer → handoff, +30s)

After S0 pretest → scoreboard. Same notebook, same `:8000`. The ADHD win: **the worst topic does not hijack forever** — spawn is an **offer** (never auto-open), at most **2** specialists, and **mild gaps stay on the scoreboard**.

Judge beats (UI in [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md)):

1. Scoreboard shows **severe + mild** (or at least gaps with `severity`).
2. **Spawn offer** appears — user picks ≤2 specialists; nothing auto-opens.
3. Work one specialist (message / optional `generate_quiz`, still cited) → **Close** → handoff lands on the orchestrator (`summary` + `scoreboard_snapshot`).
4. Mild / stale topics are still listed on the scoreboard after handoff (neglect-aware).

**S1 API** (same `:8000` `/api/v1`; Study-logic #24 on main):

- `GET|POST /api/v1/notebooks/:id/chats/orchestrator` — idempotent get-or-create (notebook open; no extra CTA)
- `GET /api/v1/notebooks/:id/chats` — listing also get-or-creates the orchestrator
- `GET /api/v1/notebooks/:id/spawn-offer` — `{ "candidates": [...], "max_spawn": 2 }`; empty `candidates` before attempts (never invented from the topic map); after pretest: ≤2, **severe-first**
- `POST /api/v1/notebooks/:id/chats/specialists` — `{ "topic_ids": ["…"] }` → `{ "chat", "warnings" }`; a third open specialist is **409** `TooManySpecialists`
- `POST /api/v1/chats/:id/messages` — `{ "text" }` or `{ "content" }` (Web alias, #31); `{ "generate_quiz": true }` still requires `citation_chunk_ids`
- `POST /api/v1/chats/:id/close` — `{ "chat", "handoff" }`
- `GET /api/v1/notebooks/:id/handoffs` — list; each handoff has `summary` + `scoreboard_snapshot`

The optional S1 block is appended to the S0 curl smoke above (same `$NOTEBOOK_ID`). It exits **non-zero** on failed S1 asserts. If S1 routes are missing (**404** / **501** on `GET …/spawn-offer`), **S0 must still pass** — the S0 echo already printed; set `NOTBOOK_SMOKE_S1=0` to skip S1. On this tree, S1 is on main, so the default is to require it.

---

## Release smoke checklist (“demo green”)

Release runs this on a **fresh shell** before calling the demo green. Maps to [`SPEC.md`](SPEC.md) §12 S0 acceptance + S1 chat-tree.

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
- [ ] S1: `GET …/spawn-offer` is empty before attempts; after pretest ≤2 candidates, severe-first
- [ ] S1: accept ≤2 specialists (offer, not auto-open); `POST …/chats/specialists` + `POST /chats/:id/close`
- [ ] S1: handoff lands on orchestrator (`summary` + `scoreboard_snapshot` on `GET …/handoffs`)
- [ ] S1: mild / stale topics stay on the scoreboard after handoff (neglect-aware)
- [ ] If S1 routes 404, S0 smoke still passes (`NOTBOOK_SMOKE_S1=0` to skip S1 asserts)
- [ ] No secrets in git; no multi-user auth / public ingress / Legal docs required for the path
- [ ] Web UI starts from DEMO install steps (`cd web && npm install && npm run dev` → `http://127.0.0.1:3000`)
- [ ] 60–90s judge click path in [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md) completes against the real `:8000` API (no mock) — S0 steps 1–6 plus S1 steps 7–13
- [ ] Home screen shows API connected (not “API unreachable”)
- [ ] `docker pull ghcr.io/charlieadair/notbook:latest` works anonymously; compose `/health` + UI load

Backend + Web install on main. Study-logic (S0 + S1) is on the `:8000` app. Judge path is local UI `:3000` + API `:8000`. Docker/GHCR is the Release publish path (issue #7) — local pull/run only.

---

## Out of scope (will block merge if required for challenge)

These are S2–S4 / later. A PR that makes any of them **required** for the judge path does not merge:

- S2 miss→explain→retest polish
- Flashcards
- Media toys (podcasts, slides, mind maps, video ingest)
- Multi-user auth
- Privacy Policy / ToS for strangers
- Public k8s / Cloudflare ingress (a **local** GHCR image for `docker compose` / `docker run` is in-scope; hosted SaaS is not)

S1 chat-tree (orchestrator, spawn offer, specialists, handoffs) **is** in scope for this demo. It lives on the same `:8000` `/api/v1` router; Web UI is on main (PR #25).

Notbook S0 + S1 is a local study harness, not a hosted product.
