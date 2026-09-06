# Notbook — Demo (S0)

Release gate for the Student Build Challenge. Contract: [`SPEC.md`](SPEC.md) §12 (S0 acceptance). Self-hosted first. No multi-user auth, no public k8s/Cloudflare ingress, no Legal/ToS for strangers.

The app stack is **not fully scaffolded yet** (`README.md`, `SPEC.md`, `bots/` only). This file is still the demo-green doc: **honest about TBD install commands** Backend/Web will pin, **fully concrete** on the judge narrative and smoke path. Release updates exact commands when scaffolds land — do not invent a fake stack.

---

## What judges should see (30s story)

Self-hosted study harness; notes stay local; every answer cites what was consumed; scoreboard shows real weaknesses.

In one sitting: upload class materials on your machine → inspect the vault (sources + chunks, not only “upload ok”) → confirm topics → take a grounded pretest → see a per-topic struggle map. If a step needs a cloud login, a public URL, or a ToS click, the demo has failed.

---

## Prerequisites

- **Machine with this repo cloned** (single-user, local).
- **Inference** — one of:
  - Local model runtime (~16GB GPU VRAM), or
  - BYO / MCP provider you already pay for.
  - Env keys are **placeholders** until Backend finalizes `.env.example`. No real secrets in git.
- **Sample materials** — one short **PDF** and one **handwritten/scan image**. Until Backend adds `fixtures/`, use any local class PDF plus a photo of handwritten notes. Expected later (names TBD, Backend-owned): e.g. `fixtures/sample.pdf` and `fixtures/handwritten.png`.

### Env keys (TBD — Backend owns names and defaults)

Copy `.env.example` → `.env` **when that file exists**. Until then, expect keys in this family (fill locally; never commit values):

| Key | Intent | Placeholder default |
| --- | --- | --- |
| `NOTBOOK_API_URL` | Study API base | `http://127.0.0.1:8000` |
| `NOTBOOK_WEB_URL` | Web UI base | `http://127.0.0.1:3000` |
| `NOTBOOK_INFERENCE_MODE` | `local` \| `mcp` \| `byo` | TBD |
| `NOTBOOK_INFERENCE_BASE_URL` | Local runtime or provider endpoint | TBD |
| `NOTBOOK_INFERENCE_MODEL` | Chat/completions model id | TBD |
| `NOTBOOK_INFERENCE_*` | Any further adapter knobs Backend pins | TBD |

Do **not** put API keys, tokens, or kubeconfigs in the repo or in this file.

---

## Install & run (self-hosted)

**Release will replace these placeholders when Backend/Web land scaffolds.** Follow the Backend README / Makefile / Compose files once they exist. Do not treat the commands below as a working stack today.

1. **Clone the repo**

   ```bash
   git clone https://github.com/charlieadair/notbook.git
   cd notbook
   ```

2. **Env file** — when Backend adds `.env.example`:

   ```bash
   cp .env.example .env
   # edit .env locally — inference mode + any provider keys stay on this machine
   ```

   Until `.env.example` exists, export the keys in the table above in your shell (or skip if you are only reading this doc).

3. **Start Study API (Backend)** — placeholder; pick whatever Backend actually ships:

   ```bash
   # TBD — one of these, once present (do not invent a stack):
   #   make api
   #   docker compose up api
   #   follow Backend README
   ```

   Default expect: `http://127.0.0.1:8000` (or the port Backend documents).

4. **Start Web UI** — placeholder:

   ```bash
   # TBD — one of these, once present:
   #   make web
   #   package-manager run (npm/pnpm/bun) from the web app dir Backend/Web name
   ```

   Default expect: `http://127.0.0.1:3000`.

5. **Health check**

   ```bash
   # Exact health path TBD (Backend). Try a dedicated health route first:
   curl -fsS "${NOTBOOK_API_URL:-http://127.0.0.1:8000}/health"
   # Then open the UI in a local browser:
   #   ${NOTBOOK_WEB_URL:-http://127.0.0.1:3000}
   ```

Both processes must bind **loopback** (or another user-controlled host). A public ingress URL is out of scope and fails the demo.

---

## 60-second judge script

UI-first. Fail the demo if any step requires **cloud multi-user login**, a **public URL**, or **Legal/ToS acceptance**.

1. Open the local UI (`http://127.0.0.1:3000` or `NOTBOOK_WEB_URL`). No account signup.
2. Create or open a notebook. Upload **one PDF** and **one handwritten/scan** image.
3. Inspect the vault: list sources (filenames + extract/OCR status) and open chunks for each source. Prove **consumption**, not only “upload succeeded.”
4. Confirm proposed topics — or skip propose and use an **explicit topic list** if the UI offers that. Pretest must stay blocked until topics are confirmed (unless the user supplied the list).
5. Start the pretest. On **at least one item**, show citations back to vault chunks (`citation_chunk_ids` → chunk text / locator / source).
6. Submit the quiz. Show the **per-topic scoreboard** update (proficiency bar **80%**; Study-logic window = **last 20 attempts** per topic).

### CLI / API smoke (~60s)

Mirrors the same path against the local Study API. Scope sketch (shapes TBD — Backend/Study-logic pin OpenAPI). Placeholders: `NOTEBOOK_ID`, ports.

**Vault (Backend)**

- `POST /notebooks/:id/sources` — PDF \| md \| paste \| image/scan
- `GET /notebooks/:id/sources` — list + extract status
- `GET /sources/:id/chunks` — inspect
- `GET /chunks/:id` — text + locator
- `POST /notebooks/:id/retrieve` — `{query}` → citable chunks

**Topics (Study-logic)**

- `POST /notebooks/:id/topics/propose`
- `POST /notebooks/:id/topics/confirm` — pretest blocked until confirmed (or explicit user list)
- `GET /notebooks/:id/topics`

**Quiz (Study-logic)**

- `POST /notebooks/:id/quizzes/pretest` (or `/quizzes`) — items **must** have `citation_chunk_ids`; drop/flag low-evidence; **409** if topics unconfirmed; **422** if insufficient evidence
- `POST /quizzes/:id/attempts` — grade → scoreboard

**Scoreboard**

- `GET /notebooks/:id/scoreboard` — per-topic; 80% bar; last-20 window

Multipart field names, JSON envelopes, and `POST /notebooks` are **Backend-owned**. This script exits **non-zero** if pretest items lack citations or the scoreboard is empty. Requires `curl` and `python3`.

```bash
#!/usr/bin/env bash
# S0 smoke — ingest → inspect → propose/confirm → pretest → attempt → scoreboard
# Run after Backend/Web pin commands. Placeholders below are intentional.
set -euo pipefail

API="${NOTBOOK_API_URL:-http://127.0.0.1:8000}"
NOTEBOOK_ID="${NOTEBOOK_ID:?set NOTEBOOK_ID to a local notebook id (UI create, or POST /notebooks once Backend adds it)}"
SMOKE_PDF="${SMOKE_PDF:-./fixtures/sample.pdf}"
SMOKE_SCAN="${SMOKE_SCAN:-./fixtures/handwritten.png}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl_json() {
  local out="$1"; shift
  local code
  code="$(curl -sS -o "$out" -w "%{http_code}" "$@")"
  echo "$code"
}

# 0) Health (path TBD — Backend). Fail if the API is down.
if ! curl -fsS "$API/health" >"$tmp/health" 2>/dev/null; then
  echo "WARN: GET /health not available yet; Backend must pin a health route" >&2
  curl -fsS -o /dev/null -w "api_root:%{http_code}\n" "$API/" || true
fi

# 1) Ingest PDF + handwritten/scan (form keys TBD — Backend).
curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/sources" \
  -F "file=@${SMOKE_PDF}" -F "type=pdf" >"$tmp/src_pdf.json"
curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/sources" \
  -F "file=@${SMOKE_SCAN}" -F "type=image" >"$tmp/src_scan.json"

# 2) List sources + extract status; require at least two sources.
curl -fsS "$API/notebooks/${NOTEBOOK_ID}/sources" >"$tmp/sources.json"
python3 - "$tmp/sources.json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
rows = data if isinstance(data, list) else data.get("sources") or data.get("items") or []
if len(rows) < 2:
    sys.stderr.write("FAIL: expected >=2 sources (PDF + scan) with extract status\n")
    sys.exit(1)
print("sources", len(rows))
PY

# 3) Inspect chunks for the first source; then one chunk body (prove consumption).
SOURCE_ID="$(python3 - "$tmp/sources.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else data.get("sources") or data.get("items") or []
print(rows[0].get("id") or rows[0].get("source_id"))
PY
)"
curl -fsS "$API/sources/${SOURCE_ID}/chunks" >"$tmp/chunks.json"
CHUNK_ID="$(python3 - "$tmp/chunks.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else data.get("chunks") or data.get("items") or []
if not rows:
    sys.stderr.write("FAIL: no chunks — upload-ok without consumption\n")
    sys.exit(1)
print(rows[0].get("id") or rows[0].get("chunk_id"))
PY
)"
curl -fsS "$API/chunks/${CHUNK_ID}" >"$tmp/chunk.json"
python3 - "$tmp/chunk.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
text = c.get("text") or c.get("content") or ""
if not str(text).strip():
    sys.stderr.write("FAIL: chunk has no text/locator payload\n")
    sys.exit(1)
print("chunk_ok", c.get("id") or c.get("chunk_id"))
PY

# Optional retrieve (citable chunks for a query).
curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/retrieve" \
  -H "Content-Type: application/json" \
  -d '{"query":"what was ingested?"}' >"$tmp/retrieve.json" || true

# 4) Propose topics, then assert pretest is blocked (409) until confirm.
curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/topics/propose" \
  -H "Content-Type: application/json" \
  -d '{}' >"$tmp/propose.json"

pre_code="$(curl_json "$tmp/pretest_blocked.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API/notebooks/${NOTEBOOK_ID}/quizzes/pretest")"
if [[ "$pre_code" != "409" ]]; then
  echo "FAIL: pretest before confirm must be 409 (got ${pre_code})" >&2
  exit 1
fi

# Confirm proposed topics (or pass an explicit list — no forced re-propose).
# Explicit-list variant (do not also require propose):
#   curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/topics/confirm" \
#     -H "Content-Type: application/json" \
#     -d '{"topics":["topic-a","topic-b"]}'
curl -fsS -X POST "$API/notebooks/${NOTEBOOK_ID}/topics/confirm" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}' >"$tmp/confirm.json"
curl -fsS "$API/notebooks/${NOTEBOOK_ID}/topics" >"$tmp/topics.json"

# 5) Pretest — items MUST include citation_chunk_ids; 422 if evidence is thin.
pre_code="$(curl_json "$tmp/pretest.json" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API/notebooks/${NOTEBOOK_ID}/quizzes/pretest")"
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
q = json.load(open(sys.argv[1]))
items = q.get("items") or q.get("questions") or []
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
print(q.get("id") or q.get("quiz_id") or "")
if not (q.get("id") or q.get("quiz_id")):
    sys.stderr.write("FAIL: pretest response has no quiz id\n")
    sys.exit(1)
PY
)"

# 6) Grade one attempt (answer shape TBD — Study-logic). Then read scoreboard.
ITEM_ID="$(python3 - "$tmp/pretest.json" <<'PY'
import json, sys
q = json.load(open(sys.argv[1]))
items = q.get("items") or q.get("questions") or []
print(items[0].get("id") or items[0].get("item_id"))
PY
)"
curl -fsS -X POST "$API/quizzes/${QUIZ_ID}/attempts" \
  -H "Content-Type: application/json" \
  -d "{\"item_id\": \"${ITEM_ID}\", \"answer\": 0}" >"$tmp/attempt.json"

curl -fsS "$API/notebooks/${NOTEBOOK_ID}/scoreboard" >"$tmp/scoreboard.json"
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

- [ ] API + Web start cleanly from DEMO install steps on a fresh shell
- [ ] Upload PDF + handwritten/scan both appear as searchable vault content
- [ ] Sources list + chunk inspect work (not only upload succeeded)
- [ ] Without explicit topics: propose waits for confirm before pretest
- [ ] With explicit topics: pretest uses them without forced re-propose
- [ ] Quiz items include `citation_chunk_ids`; low-evidence not silently invented
- [ ] Completing pretest updates visible per-topic scoreboard
- [ ] Demo narrative holds: local materials, visible consumption, grounded quiz
- [ ] No secrets in git; no multi-user auth / public ingress / Legal docs required for the path

Until Backend/Web land, the **install** boxes stay open (commands TBD). The **narrative and API path** above are the merge bar those scaffolds must hit.

---

## Out of scope (will block merge if required for challenge)

These are S4 / later. A PR that makes any of them **required** for the judge path does not merge:

- Multi-user auth
- Privacy Policy / ToS for strangers
- Public k8s / GHCR / Cloudflare ingress
- S1 chat tree (orchestrator + specialists) unless Scope opens stretch

Notbook S0 is a local study harness, not a hosted product.
