import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import { Banner } from "../components/Banner";
import { useAsync } from "../hooks/useAsync";
import { API_BASE_URL, USE_MOCK } from "../lib/config";
import { errorMessage } from "../lib/format";

export function Home() {
  const api = useApi();
  const navigate = useNavigate();
  const notebooks = useAsync(() => api.listNotebooks(), [api]);
  const health = useAsync(() => api.health(), [api]);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const notebook = await api.createNotebook(title.trim() || "Untitled notebook");
      navigate(`/notebooks/${notebook.id}/upload`);
    } catch (err) {
      setCreateError(errorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  const healthOk = health.data?.ok;
  const healthLabel = USE_MOCK
    ? "Mock API (UI-only)"
    : health.loading
      ? "Checking API…"
      : healthOk
        ? `API connected${health.data?.service ? ` · ${health.data.service}` : ""}`
        : "API unreachable";

  return (
    <div className="stack">
      <header>
        <h1>Notbook</h1>
        <p className="lede">Feed materials, inspect what was consumed, confirm topics, take a grounded pretest.</p>
      </header>

      <p className="health" title={API_BASE_URL}>
        {healthLabel}
        {!USE_MOCK && !healthOk && !health.loading ? ` · ${API_BASE_URL}` : null}
      </p>

      {health.error && !USE_MOCK ? (
        <Banner tone="error">
          Could not reach the Study API at <code>{API_BASE_URL}</code>. Start Backend locally, or run the UI with{" "}
          <code>VITE_USE_MOCK=1</code> for a client-only smoke (not real study logic).
        </Banner>
      ) : null}

      <section className="paper">
        <h2>Create a notebook</h2>
        <form className="stack" onSubmit={onCreate}>
          <div className="field">
            <label htmlFor="title">Notebook title</label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Linear algebra midterm"
              autoFocus
            />
          </div>
          {createError ? <Banner tone="error">{createError}</Banner> : null}
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={creating}>
              {creating ? "Creating…" : "Create notebook"}
            </button>
          </div>
        </form>
      </section>

      <section className="paper">
        <h2>Open an existing notebook</h2>
        {notebooks.loading ? <p className="muted">Loading…</p> : null}
        {notebooks.error ? (
          <Banner tone="error">
            Could not list notebooks. {errorMessage(notebooks.error)} If Backend is still coming up, create a notebook
            first.
          </Banner>
        ) : null}
        {!notebooks.loading && !notebooks.error && (notebooks.data?.length ?? 0) === 0 ? (
          <p className="empty">No notebooks yet. Create one above — that is the only first step.</p>
        ) : null}
        <ul className="list">
          {(notebooks.data ?? []).map((nb) => (
            <li key={nb.id} className="list-row">
              <div>
                <strong>{nb.title}</strong>
                <div className="muted">{nb.id}</div>
              </div>
              <Link className="btn" to={`/notebooks/${nb.id}/upload`}>
                Open
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
