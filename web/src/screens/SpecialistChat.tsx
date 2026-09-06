import { FormEvent, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { ChatMessage, Topic } from "../api/types";
import { Banner } from "../components/Banner";
import { ScoreRow } from "../components/ScoreRow";
import { useAsync } from "../hooks/useAsync";
import { errorMessage, formatWhen } from "../lib/format";

type Ctx = { notebookId: string };

export function SpecialistChat() {
  const { notebookId } = useOutletContext<Ctx>();
  const { chatId = "" } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composeNote, setComposeNote] = useState<string | null>(null);

  const chat = useAsync(() => api.getChat(chatId, notebookId), [api, chatId, notebookId]);
  const topics = useAsync(() => api.listTopics(notebookId), [api, notebookId]);
  const board = useAsync(() => api.getScoreboard(notebookId), [api, notebookId]);
  const messages = useAsync(() => api.listChatMessages(chatId), [api, chatId]);

  const names = new Map((topics.data ?? []).map((t: Topic) => [t.id, t.name]));
  const topicIds = chat.data?.topic_ids ?? [];
  const topicNames = topicIds.map((id) => names.get(id) ?? id);
  const slice = (board.data?.topics ?? []).filter((row) => topicIds.includes(row.topic_id));
  const bar = board.data?.proficiency_bar ?? 0.8;
  const closed = chat.data?.status === "closed";

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setBusy(true);
    setError(null);
    setComposeNote(null);
    try {
      const posted = await api.sendChatMessage(chatId, { text: content });
      setDraft("");
      if (!posted.message) {
        setComposeNote("Message endpoint is not mounted yet. You can still close this chat to send a handoff.");
      }
      await messages.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function closeChat() {
    setClosing(true);
    setError(null);
    try {
      const handoff = await api.closeChat(chatId);
      const q = handoff.id ? `?handoff=${encodeURIComponent(handoff.id)}` : "";
      navigate(`/notebooks/${notebookId}/orchestrator${q}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setClosing(false);
    }
  }

  if (chat.loading) {
    return <p className="muted">Loading focus chat…</p>;
  }

  if (!chat.data) {
    return (
      <div className="stack">
        <Banner tone="error">
          This chat was not found. S1 routes may not be mounted yet.{" "}
          <Link to={`/notebooks/${notebookId}/scoreboard`}>Back to scoreboard</Link>
        </Banner>
      </div>
    );
  }

  if (chat.data.kind === "orchestrator") {
    return (
      <div className="stack">
        <Banner>
          That id is the orchestrator root.{" "}
          <Link to={`/notebooks/${notebookId}/orchestrator`}>Open orchestrator</Link>
        </Banner>
      </div>
    );
  }

  return (
    <div className="stack">
      <header>
        <h1>{topicNames.join(", ") || "Focus chat"}</h1>
        <p className="lede">
          Specialist scope — one topic (or a tight cluster). Shared scoreboard updates live. Close to hand a
          summary back to the orchestrator.
        </p>
      </header>

      {error ? <Banner tone="error">{error}</Banner> : null}

      {slice.map((row) => (
        <ScoreRow
          key={row.topic_id}
          row={row}
          name={row.name ?? names.get(row.topic_id) ?? row.topic_id}
          bar={bar}
        />
      ))}

      <section className="paper">
        <h2>Messages</h2>
        {messages.loading ? <p className="muted">Loading messages…</p> : null}
        {!messages.loading && (messages.data?.length ?? 0) === 0 ? (
          <p className="empty">
            No messages yet. Compose below if the API supports it; otherwise close to send the handoff.
          </p>
        ) : null}
        <div className="messages">
          {(messages.data ?? []).map((message: ChatMessage) => (
            <article key={message.id || message.created_at} className={`message message-${message.role}`}>
              <p className="muted">
                {message.role} {formatWhen(message.created_at)}
              </p>
              <p>{message.text || message.content}</p>
            </article>
          ))}
        </div>
        {!closed ? (
          <form className="stack" onSubmit={send} style={{ marginTop: "1rem" }}>
            <div className="field">
              <label htmlFor="compose">Message</label>
              <textarea
                id="compose"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Ask about this topic. Close when you want the handoff."
              />
            </div>
            {composeNote ? <p className="muted">{composeNote}</p> : null}
            <div className="row">
              <button className="btn" type="submit" disabled={busy || !draft.trim()}>
                {busy ? "Sending…" : "Send"}
              </button>
              <button
                className="btn btn-ghost"
                type="button"
                disabled={busy}
                onClick={() => {
                  void (async () => {
                    setBusy(true);
                    setError(null);
                    try {
                      const posted = await api.sendChatMessage(chatId, { generate_quiz: true });
                      await messages.reload();
                      if (posted.quiz) {
                        setComposeNote(
                          `Grounded quiz generated (${posted.quiz.items.length} items, citations required). Grade via existing POST /quizzes/:id/attempts — shared scoreboard.`,
                        );
                      }
                    } catch (err) {
                      setError(errorMessage(err));
                    } finally {
                      setBusy(false);
                    }
                  })();
                }}
              >
                Generate grounded quiz
              </button>
            </div>
          </form>
        ) : (
          <Banner>This focus chat is closed. The handoff should already be on the orchestrator.</Banner>
        )}
      </section>

      <div className="row">
        {!closed ? (
          <button className="btn btn-primary" type="button" onClick={() => void closeChat()} disabled={closing}>
            {closing ? "Handing off…" : "Close & hand off"}
          </button>
        ) : (
          <Link className="btn btn-primary" to={`/notebooks/${notebookId}/orchestrator`}>
            See orchestrator handoff
          </Link>
        )}
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/orchestrator`}>
          Orchestrator
        </Link>
      </div>
    </div>
  );
}
