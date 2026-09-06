import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Chunk, Source } from "../api/types";
import { Banner } from "../components/Banner";
import { ExtractBadge } from "../components/ExtractBadge";
import { errorMessage } from "../lib/format";

type Ctx = { notebookId: string };

export function Vault() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingChunks, setLoadingChunks] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void api
      .listSources(notebookId)
      .then((rows) => {
        if (!cancelled) setSources(rows);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [api, notebookId]);

  async function openSource(sourceId: string) {
    setSelected(sourceId);
    setLoadingChunks(true);
    setError(null);
    try {
      setChunks(await api.listChunks(notebookId, sourceId));
    } catch (err) {
      setError(errorMessage(err));
      setChunks([]);
    } finally {
      setLoadingChunks(false);
    }
  }

  const active = sources.find((s) => s.id === selected);
  const totalChunks = sources.reduce((sum, s) => sum + s.chunk_count, 0);
  const failed = sources.filter((s) => s.extract_status === "failed");

  return (
    <div className="stack">
      <header>
        <h1>Vault</h1>
        <p className="lede">What the model can actually see: sources, extract status, and chunks.</p>
      </header>

      {error ? <Banner tone="error">{error}</Banner> : null}

      {sources.length === 0 ? (
        <Banner>
          Vault is empty. <Link to={`/notebooks/${notebookId}/upload`}>Upload materials</Link> before proposing topics.
        </Banner>
      ) : null}

      {sources.length > 0 && totalChunks === 0 ? (
        <Banner>
          No chunks yet. Uploads may still be extracting, or OCR failed. Stay here until a source shows a chunk count.
        </Banner>
      ) : null}

      {failed.length > 0 ? (
        <Banner tone="error">
          {failed.length === 1 ? "One source failed extract." : `${failed.length} sources failed extract.`} Re-upload a
          clearer scan or paste the text instead.{" "}
          <Link to={`/notebooks/${notebookId}/upload`}>Back to upload</Link>
        </Banner>
      ) : null}

      <section className="paper">
        <h2>Sources</h2>
        <ul className="list">
          {sources.map((source) => (
            <li key={source.id} className="list-row">
              <div>
                <strong>{source.filename}</strong>
                <div className="muted">
                  {source.chunk_count} {source.chunk_count === 1 ? "chunk" : "chunks"}
                </div>
              </div>
              <div className="row">
                <ExtractBadge status={source.extract_status} />
                <button className="btn" type="button" onClick={() => void openSource(source.id)}>
                  {selected === source.id ? "Selected" : "View chunks"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {selected ? (
        <section className="paper">
          <h2>Chunks · {active?.filename ?? selected}</h2>
          {loadingChunks ? <p className="muted">Loading chunks…</p> : null}
          {!loadingChunks && chunks.length === 0 ? (
            <p className="empty">
              No chunks for this source. If extract failed, re-upload; if it is still pending, wait and refresh.
            </p>
          ) : null}
          {chunks.map((chunk) => (
            <article key={chunk.id} className="paper">
              <p className="muted">
                {chunk.id}
                {chunk.locator ? ` · ${formatLocator(chunk.locator)}` : ""}
              </p>
              <div className="chunk">{chunk.text || "(empty chunk)"}</div>
            </article>
          ))}
        </section>
      ) : null}

      <div className="row">
        <Link className="btn btn-primary" to={`/notebooks/${notebookId}/topics`}>
          Confirm topics
        </Link>
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/upload`}>
          Add more materials
        </Link>
      </div>
    </div>
  );
}

function formatLocator(locator: Chunk["locator"]): string {
  if (!locator) return "";
  if (typeof locator === "string") return locator;
  const bits = [
    locator.label,
    locator.page != null ? `page ${locator.page}` : null,
    locator.region,
  ].filter(Boolean);
  return bits.join(" · ");
}
