# S0 web demo script

Release smoke for the Web UI. Contract: [`SPEC.md`](../SPEC.md) §§5, 9–10, 12. Prefer the **real** local Study API.

## Start

```bash
# Terminal A — Backend (vault). Use whatever Backend documents.
# Expected default: http://127.0.0.1:8000  with /api/v1

# Terminal B — Study-logic if it is a separate process (PR #1 defaults to :3000).
# If Backend already mounts study routes, skip this.

# Terminal C — Web
cd web
npm install
# Point at Backend's /api/v1 prefix (default) or Study-logic with no prefix:
#   VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
#   VITE_API_BASE_URL=http://127.0.0.1:3000
npm run dev
```

Open `http://127.0.0.1:5173`. No account. If the home screen says the API is unreachable, fix the base URL or start Backend — do not use `VITE_USE_MOCK=1` for the judge path.

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

Pretest: `POST /notebooks/{id}/quizzes/pretest` (fallback `POST /notebooks/{id}/quizzes` if that is what landed).  
409 → nudge to confirm topics. 422 → explain weak/empty vault; do not invent items.
