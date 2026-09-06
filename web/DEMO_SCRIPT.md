# S0 + S1 web demo script

Release smoke for the Web UI. Contract: [`SPEC.md`](../SPEC.md) §§5, 9–10, 12. Prefer the **real** local Study API. S0 steps 1–6 are the primary path and **must stay green**. S1 steps 7–13 are demo-bar (not stretch): spawn offer → specialist → handoff, so the worst topic does not hijack forever.

## Start

```bash
# Terminal A — Backend vault + Study-logic (merged on :8000 /api/v1)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Terminal B — Web on DEMO port 3000
cd web
npm install
# default: VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
# Study-logic is on that same /api/v1 prefix (not its standalone :3000).
npm run dev
```

Open `http://127.0.0.1:3000`. No account. Full DEMO needs Backend vault (PR #3, on main) on `:8000`. If the home screen says the API is unreachable, start that API — do not point Web at Study-logic’s standalone `:3000`, and do not use `VITE_USE_MOCK=1` for the judge path.

API curl for the same beats: [`../DEMO.md`](../DEMO.md) (S0 smoke, then the optional S1 block).

## Click path (~60–90s)

### S0 spine (must stay green)

1. **Create notebook** — title e.g. `Bio midterm`. Land on Upload.
2. **Upload PDF + paste + image**
   - Upload a short class PDF.
   - Paste a paragraph of notes (optional filename `notes.md`).
   - Upload a photo of handwritten notes (`png` / `jpg` / `webp`).
   - Confirm each source appears with `extract_status` (Extracted / Extracting / Extract failed) and a chunk count.
3. **Inspect sources / chunks** — open Vault. Click **View chunks** on the PDF and the image. You must see chunk text (consumption), not only “upload succeeded.” If a scan failed OCR, the failed badge and re-upload guidance stay visible.
4. **Propose + confirm topics** — Topics screen. **Propose topics**, edit a name if you want, **Confirm these topics**. The **Take pretest** button stays disabled until confirmed. (Or paste an explicit list and **Use this list** — no forced re-propose.)
5. **Take pretest with Show citations** — start the pretest. Answer at least one item. Click **Show citations**. Chunk ids resolve via `GET /chunks/:id` to source text. Then finish the quiz.
6. **See scoreboard** — per-topic correct rate, proficient at 80%, severity `ok | mild | severe`.

S0 steps 1–6 must stay green even when S1 routes 404.

### S1 demo bar (spawn offer → handoff)

Confirm **at least two topics** and miss enough items that the scoreboard shows a **severe** gap and a **mild** gap (or at least gaps with severity). Then:

7. **Orchestrator is get-or-create (no extra CTA)** — open the notebook and click **Focus** in the step nav (or **Orchestrator** from the scoreboard). The root chat exists without a “create orchestrator” button. `GET|POST /notebooks/:id/chats/orchestrator` (and listing chats) is idempotent.
8. **Before pretest attempts:** spawn offer is empty — no invented candidates. On Focus / scoreboard you see a “take pretest first” / no-scores nudge, not a fake offer. `GET /notebooks/:id/spawn-offer` → `{ candidates: [], max_spawn: 2 }`.
9. **After pretest:** the **Focus chats (offer)** panel lists **≤2** candidates, **severe-first**. Mild gaps remain visible on the scoreboard (not hidden by the offer).
10. **User picks ≤2** — check topics on the offer, then **Open focus chat**. Study-logic opens **one** specialist for the picked `topic_ids` (`{ chat, warnings[] }`). Specialists **never auto-open**. You may skip and keep the scoreboard. A third open specialist is refused (API **409** `TooManySpecialists`).
11. **Specialist work still cited** — send a message (API accepts `content` or `text`). Optional `generate_quiz` (API) still returns `citation_chunk_ids`; pretest **Show citations** remains the UI cite path. Grade via existing `POST /quizzes/:id/attempts` — the **shared** scoreboard updates (orchestrator and specialist read the same rows).
12. **Close specialist → handoff** — **Close & hand off**. Land on Focus / orchestrator. The handoff shows `summary` + `scoreboard_snapshot` (progress only; no unsourced lecture).
13. **Mild / stale topics still listed** — after handoff, the holistic scoreboard still shows the mild (and any stale) gaps. Worst topic did not erase the rest.

## Fail the smoke if

- Any step needs login, a public URL, or Legal/ToS
- Vault only says “uploaded” with no sources/chunks
- Pretest starts while topics are unconfirmed (UI must block; API 409 is the backstop)
- Items have no citations, or Show citations cannot load chunk text
- Scoreboard is empty after a submitted attempt
- The UI invents quiz items locally instead of calling the Study API
- S0 empty states (no notebooks / no chunks / unconfirmed topics / empty scoreboard) regress
- S1 spawn opens more than 2 specialists by default, or auto-opens windows without an offer
- Spawn offer invents candidates before any pretest attempts
- Closing a specialist does not show a handoff on the orchestrator (`summary` + `scoreboard_snapshot`) when S1 routes or mock are present
- Mild / stale topics disappear from the scoreboard after a specialist handoff

## API notes for this path

Pretest: `POST /notebooks/{id}/quizzes` only.  
Ingest: single `POST /notebooks/{id}/sources` (multipart `file` or JSON `{filename?, text}`).  
Vault inspect: `GET /notebooks/{id}/sources`, `GET /sources/{id}/chunks`, `GET /chunks/{id}`.  
409 `{ error: "topics_unconfirmed" }` → nudge to confirm topics.  
422 `{ error: "insufficient_evidence" }` → explain weak/empty vault; do not invent items.

S1 (404/501 → empty; S0 screens stay up):

- `GET|POST /notebooks/{id}/chats/orchestrator` — get-or-create
- `GET /notebooks/{id}/spawn-offer` — empty before attempts; ≤2, severe-first after
- `POST /notebooks/{id}/chats/specialists` `{ topic_ids }` → `{ chat, warnings[] }`
- `GET|POST /chats/{id}/messages` — `{ text }` or `{ content }` alias; `{ generate_quiz: true }` still cited
- `POST /chats/{id}/close` → handoff
- `GET /notebooks/{id}/handoffs`
