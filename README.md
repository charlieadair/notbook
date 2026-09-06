# Notbook

Study for your next exam efficiently!
Spend less time with your nose in textbooks,
and more time actually learning!

## Problem / Use-Case

I have ADHD and sometimes struggle to focus when I'm studying for exams.

LLMs (specifically Google Gemini) have been great tools for helping with this.
specifically, I like the ability to provide some class materials as input
(lecture notes, textbook sections, etc.) and generate multiple-choice quizzes
as a pre-test to guide my study. I can then use the output from the result of
that quiz in order to guide my studying and understand the specific things that
I need to brush up on.

This workflow allows me to focus on the exam topics that I am actually struggling
to understand and use my time much more efficiently. Additionally, LLMs are good
at supplementing information that may have been glossed over in the textbook

## Gemini Notebook: The good and the bad

### The good

The Gemini family of models has incredible multi-modal capabilities and are more
or less unmatched as far as understanding text, video and images as input.

Gemini notebook supports a plethora of different outputs including generated podcasts,
infographics, slide-books, flashcards, etc.

Gemini's harness has really great LaTeX support compared to Claude Code.

### The bad

Gemini's family of models aren't actually all that smart compared to some of the newer models.

Notebook asks you before supplementing information which is great for helping with homework questions,
but its a small and annoying barrier when preparing for exams.

## This project

I want to create a harness that supports my workflow but improves on it.

**Feed the LLM materials > Test my knowledge of those materials > Guide my study > Repeat**

This *will not* cover generating podcasts or slide-decks. This will only support generating
flashcards and quizzes.

So here is what I am imagining:

A web interface where you upload content. Simple chat window where you ask for quizzes or flashcards.
The web interface allows you to take the quizzes and ask questions throughout.

## Constraints

I want this to be an accessible tool and as such. I want to be able to run this using either local
models (expecting 16 GB of GPU accelerated memory) or use it via an MCP using the inference provider
that you already pay for.

## Spec & build team

- Product contract: [`SPEC.md`](SPEC.md) (challenge target: **S0**, self-hosted)
- Judge / Release demo gate: [`DEMO.md`](DEMO.md) (self-hosted S0 smoke path)
- Grok Bot roster (Scope, Study-logic, Backend, Web, Release): [`bots/README.md`](bots/README.md)

## Web UI (S0)

Self-hosted screens live in [`web/`](web/): notebooks, upload, vault inspect, topic confirm, pretest with citations, scoreboard.

```bash
cd web
npm install
# VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1   # default; Backend + Study-logic /api/v1
npm run dev    # http://127.0.0.1:3000  (do not bind this to Study-logic's standalone listener)
```

Judge click-path: [`web/DEMO_SCRIPT.md`](web/DEMO_SCRIPT.md). Details and mock toggle: [`web/README.md`](web/README.md).

## Acknowledgement

This project is being built with Grok Bot as part of the Student Build Challenge!

## Backend (S0 Study API)

Local vault + inference adapter lives in [`backend/`](backend/). FastAPI, SQLite, filesystem store. See [`backend/README.md`](backend/README.md) and [`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## S0 study engine

Challenge target for this repo is **S0 only** (topics, grounded pretest, scoreboard). DEMO is Web UI **:3000** + one Backend **FastAPI :8000**.

- **DEMO mount:** [`packages/study_logic`](packages/study_logic) — FastAPI router included by Backend on **:8000** `/api/v1` (`install_study_logic` / `create_router` / `from study_logic.api import router`).
- **TS reference:** [`packages/study-logic`](packages/study-logic) — types, vitest, optional offline smoke on **127.0.0.1:3001**. Not the DEMO API; does not bind :3000.

```bash
pip install -e 'packages/study_logic[dev]' && python3 -m pytest packages/study_logic
npm test
npm run build
npm start          # offline fixture smoke on 127.0.0.1:3001, not DEMO
```

