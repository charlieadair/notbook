import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Source } from "../api/types";
import { Banner } from "../components/Banner";
import { ExtractBadge } from "../components/ExtractBadge";
import { errorMessage } from "../lib/format";
import { sourceUploadFeedback, uploadFailureMessage } from "../lib/upload";

type Ctx = { notebookId: string };

const ACCEPT = ".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,application/pdf,text/markdown,text/plain,image/png,image/jpeg,image/webp";

export function Upload() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const [sources, setSources] = useState<Source[]>([]);
  const [paste, setPaste] = useState("");
  const [pasteName, setPasteName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    const next = await api.listSources(notebookId);
    setSources(next);
    return next;
  }

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

  useEffect(() => {
    if (!sources.some((s) => s.extract_status === "pending")) return;
    const timer = window.setInterval(() => {
      void refresh().catch((err) => setError(errorMessage(err)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [api, notebookId, sources]);

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      setError("Choose a PDF, markdown, text, or image file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const source = await api.uploadSource(notebookId, file);
      const feedback = sourceUploadFeedback(source);
      if (feedback.error) setError(feedback.error);
      if (feedback.note) setNote(feedback.note);
      input.value = "";
      await refresh();
    } catch (err) {
      setError(uploadFailureMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onPaste(event: FormEvent) {
    event.preventDefault();
    if (!paste.trim()) {
      setError("Paste some text first.");
      return;
    }
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const source = await api.pasteSource(notebookId, {
        filename: pasteName.trim() || undefined,
        text: paste,
      });
      const feedback = sourceUploadFeedback(source);
      if (feedback.error) setError(feedback.error);
      if (feedback.note) setNote(feedback.note);
      setPaste("");
      await refresh();
    } catch (err) {
      setError(uploadFailureMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function onRetry() {
    setError(null);
    fileInputRef.current?.focus();
  }

  const failed = sources.filter((s) => s.extract_status === "failed");
  const pending = sources.some((s) => s.extract_status === "pending");
  const hasOk = sources.some((s) => s.extract_status === "ok" && s.chunk_count > 0);

  return (
    <div className="stack">
      <header>
        <h1>Upload materials</h1>
        <p className="lede">One file or paste at a time. Then inspect what actually landed in the vault.</p>
      </header>

      {error ? (
        <Banner tone="error">
          <p>{error}</p>
          <button type="button" className="btn" onClick={onRetry} disabled={busy}>
            Try again
          </button>
        </Banner>
      ) : null}
      {note ? <Banner tone="ok">{note}</Banner> : null}
      {pending ? <Banner>Extract still running on at least one source. This list refreshes on its own.</Banner> : null}
      {failed.length > 0 ? (
        <Banner tone="error">
          OCR / extract failed for {failed.map((s) => s.filename).join(", ")}. Try a clearer photo, or re-upload as PDF /
          markdown / pasted text. Failed sources stay listed so consumption is visible.
        </Banner>
      ) : null}

      <section className="paper">
        <h2>Upload a file</h2>
        <p className="muted">PDF, markdown, text, or a photo of handwritten notes (png, jpg, webp).</p>
        <form onSubmit={onUpload} className="stack">
          <div className="field">
            <label htmlFor="file">File</label>
            <input id="file" name="file" type="file" accept={ACCEPT} ref={fileInputRef} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Uploading…" : "Upload file"}
          </button>
        </form>
      </section>

      <section className="paper">
        <h2>Paste text</h2>
        <form onSubmit={onPaste} className="stack">
          <div className="field">
            <label htmlFor="paste-name">Filename (optional)</label>
            <input
              id="paste-name"
              type="text"
              value={pasteName}
              onChange={(e) => setPasteName(e.target.value)}
              placeholder="lecture-notes.md"
            />
          </div>
          <div className="field">
            <label htmlFor="paste">Text</label>
            <textarea
              id="paste"
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder="Paste a section of notes or a textbook excerpt."
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Add pasted text
          </button>
        </form>
      </section>

      <section className="paper">
        <h2>Sources so far</h2>
        {sources.length === 0 ? (
          <p className="empty">Nothing ingested yet. Upload or paste above — that is the job of this screen.</p>
        ) : (
          <ul className="list">
            {sources.map((source) => (
              <li key={source.id} className="list-row">
                <div>
                  <strong>{source.filename}</strong>
                  <div className="muted">
                    {source.chunk_count} {source.chunk_count === 1 ? "chunk" : "chunks"}
                    {source.extract_error ? ` · ${source.extract_error}` : ""}
                  </div>
                </div>
                <ExtractBadge status={source.extract_status} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="row">
        <Link className="btn btn-primary" to={`/notebooks/${notebookId}/vault`}>
          {hasOk ? "Inspect vault" : "Inspect vault anyway"}
        </Link>
      </div>
    </div>
  );
}
