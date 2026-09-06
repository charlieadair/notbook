#!/usr/bin/env bash
# Release vault smoke: create → PDF + paste + image → list sources → chunks → get chunk → retrieve
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${BASE:-http://127.0.0.1:8000}"

echo "== health =="
curl -sf "$BASE/health" | python3 -m json.tool

echo "== create notebook =="
NOTEBOOK=$(curl -sf -X POST "$BASE/api/v1/notebooks" \
  -H 'content-type: application/json' \
  -d '{"title":"Linear Algebra"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "NOTEBOOK=$NOTEBOOK"

echo "== empty retrieve (must be []) =="
EMPTY=$(curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"spectral theorem","top_k":8}')
python3 -c 'import json,sys; assert json.loads(sys.argv[1])["chunks"]==[]' "$EMPTY"

echo "== blank query retrieve (must be [] without embedding) =="
BLANK=$(curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"   ","top_k":8}')
python3 -c 'import json,sys; assert json.loads(sys.argv[1])["chunks"]==[]' "$BLANK"

echo "== empty sample chunks (must be []) =="
SAMPLE_EMPTY=$(curl -sf "$BASE/api/v1/notebooks/$NOTEBOOK/chunks?limit=32")
python3 -c 'import json,sys; assert json.loads(sys.argv[1])==[]' "$SAMPLE_EMPTY"

echo "== upload PDF + paste + image =="
curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -F "file=@fixtures/sample.pdf;type=application/pdf" | python3 -m json.tool
curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -H 'content-type: application/json' \
  -d '{"filename":"notes.txt","text":"The spectral theorem: a real symmetric matrix is orthogonally diagonalizable."}' \
  | python3 -m json.tool
curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/sources" \
  -F "file=@fixtures/handwritten_scan.png;type=image/png" | python3 -m json.tool

echo "== list sources =="
SOURCES=$(curl -sf "$BASE/api/v1/notebooks/$NOTEBOOK/sources")
echo "$SOURCES" | python3 -m json.tool
python3 -c '
import json, sys
rows = json.loads(sys.argv[1])
types = {r["type"] for r in rows}
assert types == {"pdf", "paste", "image"}, types
for r in rows:
    assert "extract_status" in r and "chunk_count" in r
    if r["type"] == "image" and r["extract_status"] == "failed":
        assert r["chunk_count"] == 0 and r.get("error")
print("sources ok:", [(r["type"], r["extract_status"], r["chunk_count"]) for r in rows])
' "$SOURCES"

if command -v tesseract >/dev/null 2>&1; then
  python3 -c '
import json, sys
rows = json.loads(sys.argv[1])
image = next(r for r in rows if r["type"] == "image")
assert image["extract_status"] == "ok", image
assert image["chunk_count"] >= 1, image
print("ocr ok:", image["chunk_count"], "chunks")
' "$SOURCES"
  OCR_HITS=$(curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
    -H 'content-type: application/json' \
    -d '{"query":"Gram-Schmidt","top_k":8}')
  python3 -c '
import json, sys
hits = json.loads(sys.argv[1])["chunks"]
assert hits, "expected OCR text to be searchable via retrieve"
assert any("gram" in h["text"].lower() or "schmidt" in h["text"].lower() for h in hits)
print("ocr retrieve ok:", len(hits), "chunks")
' "$OCR_HITS"
else
  echo "OCR_SKIPPED"
fi

SOURCE=$(python3 -c '
import json, sys
rows = json.loads(sys.argv[1])
print(next(s["id"] for s in rows if s["chunk_count"] > 0))
' "$SOURCES")

echo "== list chunks + get chunk =="
CHUNKS=$(curl -sf "$BASE/api/v1/sources/$SOURCE/chunks")
echo "$CHUNKS" | python3 -m json.tool
CHUNK=$(python3 -c '
import json, sys
rows = json.loads(sys.argv[1])
assert rows and rows[0]["id"] and rows[0].get("locator") is not None
print(rows[0]["id"])
' "$CHUNKS")
curl -sf "$BASE/api/v1/chunks/$CHUNK" | python3 -m json.tool

echo "== sample notebook chunks =="
SAMPLED=$(curl -sf "$BASE/api/v1/notebooks/$NOTEBOOK/chunks?limit=32")
echo "$SAMPLED" | python3 -m json.tool
python3 -c '
import json, sys
rows = json.loads(sys.argv[1])
assert rows, "expected sample chunks after ingest"
for row in rows:
    assert row.get("id") and row.get("source_id") and row.get("text")
    assert "locator" in row and "source_filename" in row
    assert "score" not in row
print("sample chunks ok:", len(rows))
' "$SAMPLED"

echo "== retrieve =="
RETRIEVED=$(curl -sf -X POST "$BASE/api/v1/notebooks/$NOTEBOOK/retrieve" \
  -H 'content-type: application/json' \
  -d '{"query":"spectral theorem","top_k":8}')
echo "$RETRIEVED" | python3 -m json.tool
python3 -c '
import json, sys
hits = json.loads(sys.argv[1])["chunks"]
assert hits, "expected citable chunks"
assert all(h.get("id") and h.get("score", 0) > 0 for h in hits)
print("retrieve ok:", len(hits), "chunks")
' "$RETRIEVED"

echo "SMOKE_OK"
