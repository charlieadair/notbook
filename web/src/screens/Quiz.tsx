import { FormEvent, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Chunk, GeneratedQuiz, QuizItem } from "../api/types";
import { Banner } from "../components/Banner";
import { errorMessage } from "../lib/format";
import { pretestGateMessage } from "./Topics";

type Ctx = { notebookId: string };

type ItemState = {
  selected?: string;
  submitted?: boolean;
  correct?: boolean;
};

export function Quiz() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const navigate = useNavigate();
  const [quiz, setQuiz] = useState<GeneratedQuiz | null>(null);
  const [index, setIndex] = useState(0);
  const [itemState, setItemState] = useState<Record<string, ItemState>>({});
  const [showCites, setShowCites] = useState(false);
  const [chunks, setChunks] = useState<Record<string, Chunk | "loading" | "error">>({});
  const [error, setError] = useState<string | null>(null);
  const [gate, setGate] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const item = quiz?.items[index];
  const state = item ? itemState[item.id] : undefined;
  const last = quiz ? index >= quiz.items.length - 1 : false;

  async function startPretest() {
    setBusy(true);
    setError(null);
    setGate(null);
    try {
      const next = await api.createPretest(notebookId);
      setQuiz(next);
      setIndex(0);
      setItemState({});
      setShowCites(false);
    } catch (err) {
      const gated = pretestGateMessage(err);
      if (gated) setGate(gated);
      else setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!quiz || !item || !state?.selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.submitAttempt(quiz.quiz.id, {
        item_id: item.id,
        selected_choice_id: state.selected,
      });
      setItemState((prev) => ({
        ...prev,
        [item.id]: { ...prev[item.id], submitted: true, correct: result.attempt.correct },
      }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleCitations() {
    const next = !showCites;
    setShowCites(next);
    if (!next || !item) return;
    for (const chunkId of item.citation_chunk_ids) {
      if (chunks[chunkId]) continue;
      setChunks((prev) => ({ ...prev, [chunkId]: "loading" }));
      try {
        const chunk = await api.getChunk(chunkId);
        setChunks((prev) => ({ ...prev, [chunkId]: chunk }));
      } catch {
        setChunks((prev) => ({ ...prev, [chunkId]: "error" }));
      }
    }
  }

  function goNext() {
    if (!quiz) return;
    if (last) {
      navigate(`/notebooks/${notebookId}/scoreboard`);
      return;
    }
    setIndex((i) => i + 1);
    setShowCites(false);
  }

  if (!quiz) {
    return (
      <div className="stack">
        <header>
          <h1>Pretest</h1>
          <p className="lede">One question at a time. Citations stay hidden until you ask.</p>
        </header>
        {gate ? (
          <Banner tone="error">
            {gate}{" "}
            {isTopicsGate(gate) ? <Link to={`/notebooks/${notebookId}/topics`}>Confirm topics</Link> : (
              <Link to={`/notebooks/${notebookId}/upload`}>Add materials</Link>
            )}
          </Banner>
        ) : null}
        {error ? <Banner tone="error">{error}</Banner> : null}
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={() => void startPretest()} disabled={busy}>
            {busy ? "Building pretest…" : "Start pretest"}
          </button>
          <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/topics`}>
            Back to topics
          </Link>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="stack">
        <Banner>This pretest has no items.</Banner>
        <Link className="btn btn-primary" to={`/notebooks/${notebookId}/scoreboard`}>
          Open scoreboard
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <header>
        <h1>Pretest</h1>
        <p className="lede">
          Question {index + 1} of {quiz.items.length}
        </p>
      </header>

      {error ? <Banner tone="error">{error}</Banner> : null}

      <section className="paper">
        <h2>{item.stem}</h2>
        <form onSubmit={submit}>
          <div className="choices" role="radiogroup" aria-label="Answer choices">
            {item.choices.map((choice) => {
              const chosen = state?.selected === choice.id;
              const showResult = Boolean(state?.submitted);
              const isCorrectChoice = item.correct_choice_id === choice.id;
              const cls = [
                "choice",
                showResult && isCorrectChoice ? "choice-correct" : "",
                showResult && chosen && !state?.correct ? "choice-wrong" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <label key={choice.id} className={cls}>
                  <input
                    type="radio"
                    name="choice"
                    value={choice.id}
                    checked={chosen}
                    disabled={state?.submitted}
                    onChange={() =>
                      setItemState((prev) => ({ ...prev, [item.id]: { ...prev[item.id], selected: choice.id } }))
                    }
                  />
                  <span>{choice.text}</span>
                </label>
              );
            })}
          </div>
          {!state?.submitted ? (
            <button className="btn btn-primary" type="submit" disabled={busy || !state?.selected}>
              {busy ? "Saving…" : "Submit answer"}
            </button>
          ) : (
            <Banner tone={state.correct ? "ok" : "error"}>
              {state.correct ? "Correct." : "Incorrect."}
              {item.rationale ? ` ${item.rationale}` : ""}
            </Banner>
          )}
        </form>
      </section>

      <section className="paper">
        <button className="btn" type="button" onClick={() => void toggleCitations()}>
          {showCites ? "Hide citations" : "Show citations"}
        </button>
        {showCites ? <CitationList item={item} chunks={chunks} /> : null}
      </section>

      {state?.submitted ? (
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={goNext}>
            {last ? "See scoreboard" : "Next question"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function CitationList({
  item,
  chunks,
}: {
  item: QuizItem;
  chunks: Record<string, Chunk | "loading" | "error">;
}) {
  if (!item.citation_chunk_ids.length) {
    return <p className="empty">This item has no citation_chunk_ids — that should not happen on a grounded pretest.</p>;
  }
  return (
    <div className="stack" style={{ marginTop: "0.85rem" }}>
      {item.citation_chunk_ids.map((chunkId) => {
        const chunk = chunks[chunkId];
        return (
          <article key={chunkId}>
            <p className="muted">{chunkId}</p>
            {chunk === "loading" || chunk == null ? <p className="muted">Loading chunk…</p> : null}
            {chunk === "error" ? (
              <Banner tone="error">Could not load this chunk from GET /chunks/{chunkId}.</Banner>
            ) : null}
            {chunk && chunk !== "loading" && chunk !== "error" ? (
              <div className="chunk">
                {chunk.source_label ? `${chunk.source_label}\n\n` : ""}
                {chunk.text}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function isTopicsGate(message: string): boolean {
  return /confirm topics/i.test(message);
}
