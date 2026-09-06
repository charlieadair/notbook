#!/usr/bin/env bash
set -euo pipefail

# Offline fixture smoke (default :3001). DEMO API is Backend :8000.
BASE="${1:-http://127.0.0.1:3001}"
API="$BASE/api/v1"

echo "== health"
curl -sS "$API/health"
echo

echo "== propose (inferred, unconfirmed)"
curl -sS -X POST "$API/notebooks/nb_bio/topics/propose"
echo

echo "== quizzes before confirm (expect 409 TopicsUnconfirmed)"
curl -sS -X POST "$API/notebooks/nb_bio/quizzes"
echo

echo "== confirm inferred topics"
curl -sS -X POST "$API/notebooks/nb_bio/topics/confirm"
echo

echo "== list topics"
curl -sS "$API/notebooks/nb_bio/topics"
echo

echo "== create pretest"
QUIZ_JSON="$(curl -sS -X POST "$API/notebooks/nb_bio/quizzes")"
echo "$QUIZ_JSON"

QUIZ_ID="$(node -e "const j=JSON.parse(process.argv[1]); process.stdout.write(j.quiz.id)" "$QUIZ_JSON")"
ITEM_ID="$(node -e "const j=JSON.parse(process.argv[1]); process.stdout.write(j.items[0].id)" "$QUIZ_JSON")"
CHOICE_ID="$(node -e "const j=JSON.parse(process.argv[1]); process.stdout.write(j.items[0].correct_choice_id)" "$QUIZ_JSON")"

echo
echo "== grade attempt"
curl -sS -X POST "$API/quizzes/${QUIZ_ID}/attempts" \
  -H 'content-type: application/json' \
  -d "{\"item_id\":\"${ITEM_ID}\",\"selected_choice_id\":\"${CHOICE_ID}\"}"
echo

echo "== scoreboard"
curl -sS "$API/notebooks/nb_bio/scoreboard"
echo

echo "== empty vault (expect 422 InsufficientEvidence)"
curl -sS -X POST "$API/notebooks/nb_empty/topics/confirm" \
  -H 'content-type: application/json' \
  -d '{"names":["Mitosis"]}'
echo
curl -sS -X POST "$API/notebooks/nb_empty/quizzes"
echo
