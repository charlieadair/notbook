# S0 web demo script

Release smoke for the Web UI. Contract: [`SPEC.md`](../SPEC.md) §§5, 9–10, 12. Prefer the **real** local Study API.

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
npm run dev
```

Open `http://127.0.0.1:3000`. No account. If the home screen says the API is unreachable, start Backend — do not use `VITE_USE_MOCK=1` for the judge path.

## Click path (~60s)

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

## Fail the smoke if

- Any step needs login, a public URL, or Legal/ToS
- Vault only says “uploaded” with no sources/chunks
- Pretest starts while topics are unconfirmed (UI must block; API 409 is the backstop)
- Items have no citations, or Show citations cannot load chunk text
- Scoreboard is empty after a submitted attempt
- The UI invents quiz items locally instead of calling the Study API

## API notes for this path

Pretest: `POST /notebooks/{id}/quizzes` only.  
Ingest: multipart `POST /notebooks/{id}/sources/upload`, JSON `POST /notebooks/{id}/sources/paste`.  
Vault inspect: `GET /notebooks/{id}/sources`, `GET /notebooks/{id}/sources/{source_id}/chunks`, `GET /chunks/{id}`.  
409 `{ error: "topics_unconfirmed" | "TopicsUnconfirmed" }` → nudge to confirm topics.  
422 `{ error: "insufficient_evidence" | "InsufficientEvidence" }` → explain weak/empty vault; do not invent items.
