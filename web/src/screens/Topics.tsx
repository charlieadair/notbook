import { FormEvent, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import { isApiError } from "../api/errors";
import type { Topic } from "../api/types";
import { Banner } from "../components/Banner";
import { errorMessage } from "../lib/format";

type Ctx = { notebookId: string };

export function Topics() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [names, setNames] = useState<string[]>([]);
  const [explicit, setExplicit] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .listTopics(notebookId)
      .then((rows) => {
        if (cancelled) return;
        setTopics(rows);
        setNames(rows.map((t) => t.name));
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [api, notebookId]);

  const confirmed = topics.length > 0 && topics.every((t) => t.confirmed);
  const namesDirty = topics.some((t, i) => (names[i] ?? "") !== t.name);

  async function propose() {
    setBusy(true);
    setError(null);
    try {
      const rows = await api.proposeTopics(notebookId);
      setTopics(rows);
      setNames(rows.map((t) => t.name));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmProposed() {
    setBusy(true);
    setError(null);
    try {
      const rows = namesDirty
        ? await api.confirmTopics(notebookId, { names: names.map((n) => n.trim()).filter(Boolean) })
        : await api.confirmTopics(notebookId, { topic_ids: topics.map((t) => t.id) });
      setTopics(rows);
      setNames(rows.map((t) => t.name));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmExplicit(event: FormEvent) {
    event.preventDefault();
    const list = explicit
      .split(/[\n,]/)
      .map((n) => n.trim())
      .filter(Boolean);
    if (!list.length) {
      setError("Add at least one topic name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rows = await api.confirmTopics(notebookId, { names: list });
      setTopics(rows);
      setNames(rows.map((t) => t.name));
      setExplicit("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header>
        <h1>Topics</h1>
        <p className="lede">The pretest stays blocked until you confirm what the exam covers.</p>
      </header>

      {error ? <Banner tone="error">{error}</Banner> : null}

      {!confirmed ? (
        <Banner>
          Topics are not confirmed. Propose from the vault, edit names if needed, then confirm. Or type an explicit list
          and skip propose.
        </Banner>
      ) : (
        <Banner tone="ok">Topic map confirmed. You can start the pretest.</Banner>
      )}

      <section className="paper">
        <h2>From materials</h2>
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={() => void propose()} disabled={busy}>
            {topics.length ? "Re-propose topics" : "Propose topics"}
          </button>
        </div>
        {topics.length === 0 ? (
          <p className="empty">No topics yet. Propose from the vault, or enter an explicit list below.</p>
        ) : (
          <ul className="list">
            {topics.map((topic, index) => (
              <li key={topic.id} className="list-row">
                <div className="field">
                  <label htmlFor={`topic-${topic.id}`} className="sr-only">
                    Topic {index + 1}
                  </label>
                  <input
                    id={`topic-${topic.id}`}
                    type="text"
                    value={names[index] ?? topic.name}
                    onChange={(e) => {
                      const next = [...names];
                      next[index] = e.target.value;
                      setNames(next);
                    }}
                  />
                </div>
                <span className={`badge ${topic.confirmed ? "badge-ok" : "badge-pending"}`}>
                  {topic.confirmed ? "Confirmed" : "Unconfirmed"}
                </span>
              </li>
            ))}
          </ul>
        )}
        {topics.length > 0 ? (
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={() => void confirmProposed()} disabled={busy}>
              Confirm these topics
            </button>
          </div>
        ) : null}
      </section>

      <section className="paper">
        <h2>Or set an explicit list</h2>
        <p className="muted">Comma or newline separated. This writes a confirmed map and skips re-propose.</p>
        <form onSubmit={confirmExplicit} className="stack">
          <div className="field">
            <label htmlFor="explicit">Topic names</label>
            <textarea
              id="explicit"
              value={explicit}
              onChange={(e) => setExplicit(e.target.value)}
              placeholder={"Eigenvalues\nLinear regression"}
            />
          </div>
          <button className="btn" type="submit" disabled={busy}>
            Use this list
          </button>
        </form>
      </section>

      <div className="row">
        {confirmed ? (
          <Link className="btn btn-primary" to={`/notebooks/${notebookId}/quiz`}>
            Take pretest
          </Link>
        ) : (
          <button className="btn btn-primary" type="button" disabled>
            Take pretest (confirm topics first)
          </button>
        )}
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/vault`}>
          Back to vault
        </Link>
      </div>
    </div>
  );
}

export function pretestGateMessage(err: unknown): string | null {
  if (isApiError(err) && err.isTopicsUnconfirmed) {
    return "Confirm topics before starting the pretest.";
  }
  if (isApiError(err) && err.isInsufficientEvidence) {
    return "Not enough vault evidence to ground a pretest. Add more materials or wait for extract to finish.";
  }
  return null;
}
