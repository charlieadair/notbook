# Notbook — Product Spec

Study harness for exam prep: grounded quizzes and flashcards, a durable struggle map, and orchestrator + specialist chats so one weak topic cannot hijack the whole session.

**Status:** challenge-scoped draft  
**Approach:** single-app study OS (staged delivery), **self-hosted first**  
**Challenge target:** **S0 + S1** (Charlie override 2026-09-06)  
**Non-goals (challenge):** podcasts, slides, mind maps, video ingest, multi-user SaaS, public k8s deploy, Legal/ToS for strangers  

Bot roster (how we build): see [`bots/README.md`](bots/README.md).

---

## 1. Problem

NotebookLM (and similar Gemini harnesses) are strong at multimodal ingest and media generation, but weak at the loop that actually helps ADHD exam study:

1. Feed class materials  
2. Test knowledge  
3. Guide study from results  
4. Repeat  

Observed failures to fix:

| Failure | Effect |
| --- | --- |
| Weaker / locked model | Shallow or wrong explanations for hard STEM |
| “Ask before supplementing” | Friction when the goal is exam prep, not homework purity |
| No durable weak-topic memory | Each session restarts from zero |
| Thin quiz quality | Paraphrase recall; not exam-shaped; poorly grounded |
| Fixation on the worst miss | Mild gaps starve while one topic is drilled forever |
| Cloud / model lock-in | No local 16GB path; cannot bring your own inference |
| Opaque consumption | Hard to know what the model actually read or used |
| Output sprawl | Podcasts/slides compete with active retrieval |

---

## 2. Goals

### Primary loop

**Materials → grounded pretest → struggle map → focus (or light remediation) → retest → updated map**

### Product goals

1. **Grounding over eloquence** — Answers and items prefer “source X says Y” over freeform model knowledge. Prefer cited retrieval to unaugmented explanation.
2. **Inspectable consumption** — The user can see which files were ingested, which chunks exist, and which chunks grounded a given quiz item or explanation. No black-box “the bot ate my PDF.”
3. **Persistent weak-topic memory** — Topic scores and miss history survive across sessions (Approach A).
4. **Controllable, source-tied quizzes** — Difficulty and coverage tied to the vault and confirmed topic map (Approach B).
5. **Orchestrator + specialists** — Root chat keeps the broad struggle overview; deep work happens in child chats that report back (**S1**).
6. **Time-boxed sessions with measurable lift** — A session can finish in ~25–45 minutes with updated scores; across sessions, weak topics move toward a clear proficiency bar (default **80%** on recent items for that topic).
7. **Open inference** — Run on local models (~16GB GPU VRAM) **or** via MCP / the user’s existing paid provider.

### Challenge scope vs later

| Now (challenge) | Later (GTM door — not started) |
| --- | --- |
| Self-hosted / single-user on your machine | Multi-user hosted + auth + tenant isolation |
| Local or BYO inference | Shared inference with retention policy |
| Inspectable local vault | Privacy Policy / ToS, Legal bot, public ingress |
| S0 demo narrative | CI/CD → GHCR → marmalade + Cloudflare tunnel |

Leaving the door open means: keep a clean inference adapter and data model; do **not** build hosted auth, Legal, or cluster deploy during the challenge.

### Explicitly out of scope (challenge / near-term)

- Generated podcasts, slide decks, infographics, mind maps  
- Full multimodal ingest (lecture video, rich slide decks)  
- Multi-user / classroom SaaS  
- Public Kubernetes deploy, GHCR→cluster CI/CD, Cloudflare public ingress  
- Privacy Policy / ToS for third-party users (no strangers on your box yet)  
- Replacing a full LMS or Anki (export may come later)

### Well-defined but secondary (ship after spine)

**Miss → explain → retest** inside a chat: on a wrong answer, grounded explanation + immediate follow-up item(s) on the same miss before moving on. Required behavior; not the first milestone (**S2**).

---

## 3. Users & success

**Primary user:** Charlie (ADHD, STEM exam prep).

**Challenge demo audience:** Judges / peers who need a 30-second story: *self-hosted study harness; notes stay local; every answer cites what was consumed; scoreboard shows real weaknesses.*

**Session success (time-boxed):** In one sitting, ingest or open a notebook, confirm topics (if needed), take a pretest, see a struggle map, optionally open focus chats and receive handoffs, leave with updated scores.

**Arc success (measurable lift):** Over multiple sessions, topic scores on previously weak areas rise; mild gaps stay visible so they are not neglected.

---

## 4. Core concepts

### Notebook

A container for one course / exam prep effort: uploaded materials, vault chunks, topic map, chats, and the struggle scoreboard.

### Vault (RAG store)

Chunked, embedded representation of ingested materials. Obsidian-*style* in spirit (durable, **inspectable** knowledge), implemented as an app-owned store in v1 (not a hard dependency on the user’s Obsidian vault).

**Inspectability requirements (S0):**

- List sources (original filenames) and whether OCR/extract succeeded  
- Browse or search chunks tied to a source  
- On each quiz item / explanation, show citation(s) back to chunk + source  
- Prefer surfacing “model context for this turn” (chunk ids / excerpts used) over hiding the prompt stuffing  

Every generated quiz item and teaching turn should be able to cite vault chunks. When evidence is thin, the system says so rather than inventing a confident lecture.

### Topic map

Labeled units of study for this notebook (e.g. eigenvalues, linear regression).

**How topics are set:**

1. **Explicit win:** If the user states exam coverage (“pretest; covers these three topics”), use that map.  
2. **Otherwise:** After ingest, the system proposes topics from materials and **asks the user to confirm** (“I’m seeing these three topics — does that match class?”). User corrections rewrite the map before the pretest.

Hybrid refinement later: coarse buckets from the user; finer subtopics suggested when misses cluster — not required for S0 as long as confirm-on-propose works.

### Struggle scoreboard

Per-topic stats derived primarily from quiz/flashcard outcomes (correct/incorrect, recency, severity). Shared by orchestrator and specialists — **source of truth for “where you’re weak.”**

Default proficiency bar: **≥ 80%** on a recent window of items for that topic (exact window tunable; specify in implementation as e.g. last N items or last M days).

### Orchestrator chat (root) — S1

Owns: whole-notebook context, topic confirmation, pretest generation, struggle overview, light remediation on mild gaps, and offers to spawn specialists for severe gaps.

Must **not** collapse into endless drill on a single worst topic.

### Specialist chat (child) — S1

Owns: deep work on one (or tightly related) topic(s). Uses the same vault + scoreboard. On meaningful progress or explicit close, sends an **auto handoff summary** to the orchestrator. Scores update continuously via the shared scoreboard.

### Tree shape

```
Notebook
├── Vault (materials → chunks)     ← inspectable
├── Topic map (confirmed)
├── Struggle scoreboard
├── Orchestrator chat              ← S1
└── Specialist chats               ← S1
```

---

## 5. User flows

### 5.1 Ingest

1. User creates/opens a notebook and uploads materials.  
2. **S0 accept:** PDF, markdown, pasted text; **scans/photos of handwritten notes** (OCR → text into vault).  
3. System chunks, embeds, stores with source pointers (file, page/region when available).  
4. UI shows sources + chunk counts (inspectability).  
5. If no explicit topic list yet → propose topics → user confirms/edits.

### 5.2 Pretest

1. User asks for a pretest (or accepts the post-confirm prompt).  
2. System generates grounded multiple-choice (and optionally short) items tagged to topics, citing vault chunks.  
3. User takes the quiz in the UI; each item can reveal its citations.  
4. Scoreboard updates; system summarizes mild vs severe gaps.

### 5.3 Struggle offer (spawn) — S1

When severity warrants it, orchestrator asks something like:

> You missed 2 on linear regression and 5 on eigenvalues. Open focus chats for those topics? I’ll keep the broad map here and handle the lighter gaps.

User can accept all, some, or none. Default suggest at most **2** specialists per session.

### 5.4 Focus session — S1

1. Specialist chat opens with topic scope + relevant vault slice + current scores.  
2. Specialist drills that topic with grounded items and cited explanations (full miss → explain → retest polish is S2).  
3. Scoreboard updates live.  
4. On close or milestone: auto handoff summary lands in orchestrator.

### 5.5 Return visit

1. Open notebook → see scoreboard (+ last handoffs when S1 exists).  
2. Suggest what to drill without ignoring second-tier weaknesses (severity **and** neglect).

---

## 6. Grounding rules

1. Prefer retrieval-augmented answers; attach citations (chunk id / source label) on quiz rationales and explanations.  
2. Voice: “I think it works this way because [source] says X, Y, Z,” not an unsourced textbook lecture.  
3. If retrieval confidence is low: say so; ask to upload/clarify; do not silently fill from parametric knowledge as if it were course truth.  
4. Explicit opt-in only: `supplement=true` on quiz generate may fetch labeled web snippets (SearXNG) as a thin-vault hedge. Vault remains the default and is still required (`citation_chunk_ids`). Web is cited separately (`web_citations` URL/title/snippet) and is never silent course truth. Not S2 flashcards/media.  
5. Never hide what was retrieved for a graded or teaching turn when the UI can show it.

Quiz generation must pull from vault evidence for the tagged topic. Items without adequate support are dropped or flagged, not invented.

---

## 7. System architecture (logical)

```
┌─────────────────────────────────────────────────────────┐
│  Web UI                                                  │
│  upload · vault browser · quiz · scoreboard · cites      │
└─────────────┬───────────────────────────────┬───────────┘
              │                               │
              ▼                               ▼
┌─────────────────────┐           ┌─────────────────────┐
│  Study API          │           │  Inference adapter  │
│  notebooks, topics,│◄─────────►│  local OR MCP / BYO │
│  quizzes, scores,   │           │  provider           │
│  (chats S1+)        │           └─────────────────────┘
└─────────────┬───────┘
              │
              ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Vault (local)      │     │  App DB (local)     │
│  files, chunks,     │     │  notebooks, topics,│
│  embeddings, OCR    │     │  attempts, …        │
└─────────────────────┘     └─────────────────────┘
```

**Inference adapter (DIP):** One interface for chat/completions and embeddings. Implementations: local runtime and MCP/remote. Policy never hardcodes a vendor. This is the main “GTM door” seam for a future hosted deployment.

**Separation of concerns:**

| Unit | Responsibility | Challenge owner bot |
| --- | --- | --- |
| Ingest / OCR | Files → text → chunks | Backend |
| Vault / retrieve | Embed, search, cite, expose for UI | Backend |
| Topic service | Propose, confirm, store map | Study-logic |
| Quiz engine | Generate, serve, grade, tag topics | Study-logic |
| Scoreboard | Aggregate attempts → per-topic state | Study-logic |
| Chat tree | Orchestrator / specialists / handoffs | Study-logic (S1) |
| UI | Vault browser, quiz, citations, scoreboard | Web |
| Scope / merge bar | S0 + S1; reject S2–S4 creep | Scope + Release |

---

## 8. Staged delivery

| Stage | Ships | Challenge? |
| --- | --- | --- |
| **S0 — Spine** | Ingest (text + handwriting OCR), **inspectable vault**, topic propose/confirm, grounded pretest, quiz UI, scoreboard | **Required demo** |
| **S1 — Tree** | Orchestrator spawn offers, specialist chats, auto handoff + shared scores, neglect-aware suggestions | **Required for demo (Charlie override)** |
| **S2 — Teaching polish** | Miss → explain → retest UX, difficulty controls, flashcards, export | After challenge |
| **S3 — Multimodal** | Video/slides ingest (only if still wanted) | After challenge |
| **S4 — Hosted GTM door** | Multi-user auth, tenant isolation, Privacy/ToS, GHCR→k8s→Cloudflare public ingress | Explicitly deferred |

---

## 9. Constraints

- **Self-hosted for challenge:** materials and vault stay on the user’s machine (or user-controlled paths).  
- Accessible: local (~16GB GPU VRAM) **or** MCP / already-paid inference.  
- Outputs: **quizzes and flashcards only** (flashcards in S2).  
- Keep the first viewport oriented to **one job** (study), not a dashboard of toys.  
- Build via specialized Grok Bots ([`bots/`](bots/README.md)); Scope + Release gate merges to S0.

---

## 10. UX principles (ADHD)

- One primary action per screen state (take pretest / browse vault / continue).  
- Struggle map and **what was consumed** visible without digging.  
- Spawn is an **offer**, not an automatic explosion of windows (S1).  
- Default cap: suggest at most **2** specialist chats per session unless the user asks for more.  
- Orchestrator keeps second-tier topics on the scoreboard so they are not forgotten.

---

## 11. Data (minimal)

Conceptual records (storage tech chosen by Backend/Web during S0; keep local):

- `Notebook` — id, title, created  
- `Source` — notebook_id, filename, type, raw/extracted text ref, extract status  
- `Chunk` — source_id, text, embedding, locator  
- `Topic` — notebook_id, name, confirmed, parent?  
- `Quiz` / `Item` — topic tags, stem, choices, answer, citation chunk ids  
- `Attempt` — item_id, correct?, timestamp, chat_id?  
- `TopicScore` — derived or cached from attempts  
- `Chat` / `Handoff` — S1+  

---

## 12. Testing & acceptance

**S0 acceptance (challenge bar)**

- [ ] Upload PDF + handwritten scan; both appear as searchable vault content  
- [ ] User can list sources and inspect chunks (not only “upload succeeded”)  
- [ ] Without explicit topics, system proposes topics and waits for confirm before pretest  
- [ ] With explicit topics, pretest uses those without forcing re-propose  
- [ ] Quiz items cite vault chunks; low-evidence items are not silently invented  
- [ ] Completing a pretest updates a visible per-topic scoreboard  
- [ ] Demo narrative holds: local materials, visible consumption, grounded quiz  

**S1 acceptance (demo bar)**

- [ ] After pretest, orchestrator offers focus chats proportional to severity  
- [ ] Specialist progress updates the shared scoreboard  
- [ ] Closing/milestoning a specialist writes an auto handoff into the orchestrator  
- [ ] A later session still shows mild gaps that were not the “worst” topic  

**Grounding acceptance**

- [ ] Spot-check: explanations quote or paraphrase cited chunks; refusal/hedge when vault is empty for a topic  

---

## 13. Open decisions (bots resolve under Scope)

1. Concrete stack (web framework, vector store, OCR engine, local runtime).  
2. Exact score window for the 80% bar and “neglect” half-life.  
3. Whether flashcards share the same attempt model as quiz items (S2).  
4. Export formats (Anki/JSON) — post-S2.  
5. Obsidian folder sync — nice-to-have; not required.  
6. Hosted deploy details — **S4 only**; do not bikeshed during challenge.

---

## 14. Summary

Notbook is a **self-hosted, inspectable, scoreboard-driven study OS**: confirm what the exam covers, test against a vault you can see, keep a holistic struggle map, and delegate deep holes to specialist chats — without Gemini-style fixation or NotebookLM’s media distractions. The Student Build Challenge ships **S0 + S1**; **S2–S4** stay deferred. Hosted go-to-market is a deferred door, not the current build.
