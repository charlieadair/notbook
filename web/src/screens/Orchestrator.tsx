import { useMemo } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Chat, Handoff, Topic, TopicScore } from "../api/types";
import { Banner } from "../components/Banner";
import { ScoreRow } from "../components/ScoreRow";
import { SpawnOfferPanel } from "../components/SpawnOfferPanel";
import { useAsync } from "../hooks/useAsync";
import { errorMessage, formatPercent, formatWhen } from "../lib/format";

type Ctx = { notebookId: string };

export function Orchestrator() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const [params] = useSearchParams();
  const highlightId = params.get("handoff");

  const board = useAsync(() => api.getScoreboard(notebookId), [api, notebookId]);
  const topics = useAsync(() => api.listTopics(notebookId), [api, notebookId]);
  const chats = useAsync(() => api.listChats(notebookId), [api, notebookId]);
  const handoffs = useAsync(() => api.listHandoffs(notebookId), [api, notebookId]);
  const orchestrator = useAsync(() => api.getOrCreateOrchestrator(notebookId), [api, notebookId]);

  const names = new Map((topics.data ?? []).map((t: Topic) => [t.id, t.name]));
  const rows = board.data?.topics ?? [];
  const bar = board.data?.proficiency_bar ?? 0.8;
  const windowSize = board.data?.window ?? 20;
  const specialists = (chats.data ?? []).filter((c: Chat) => c.kind === "specialist");
  const openSpecialists = specialists.filter((c) => c.status === "open");
  const landing = useMemo(
    () => (handoffs.data ?? []).slice().sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [handoffs.data],
  );
  const highlighted = landing.find((h) => h.id === highlightId) ?? landing[0];

  return (
    <div className="stack">
      <header>
        <h1>Orchestrator</h1>
        <p className="lede">
          Holistic struggle map for this notebook. Specialists drill a topic; they report back here. Shared
          scoreboard is the source of truth (last {windowSize} attempts, proficient at {formatPercent(bar)}).
        </p>
      </header>

      {orchestrator.error ? (
        <p className="muted">
          Study-logic S1 orchestrator route is not mounted yet ({errorMessage(orchestrator.error)}). S0 scoreboard
          still works.
        </p>
      ) : null}

      {board.error ? <Banner tone="error">{errorMessage(board.error)}</Banner> : null}
      {board.loading ? <p className="muted">Loading scoreboard…</p> : null}

      {!board.loading && rows.length === 0 ? (
        <Banner>
          No topic scores yet. Take a pretest so the orchestrator has a map.{" "}
          <Link to={`/notebooks/${notebookId}/quiz`}>Start pretest</Link>
        </Banner>
      ) : null}

      {rows.map((row) => (
        <ScoreRow
          key={row.topic_id}
          row={row}
          name={row.name ?? names.get(row.topic_id) ?? row.topic_id}
          bar={bar}
        />
      ))}

      {rows.length > 0 ? <SpawnOfferPanel notebookId={notebookId} /> : null}

      {openSpecialists.length > 0 ? (
        <section className="paper">
          <h2>Open focus chats</h2>
          <ul className="list">
            {openSpecialists.map((chat) => (
              <li key={chat.id} className="list-row">
                <div>
                  <strong>{topicLabel(chat, names)}</strong>
                  <div className="muted">{chat.id}</div>
                </div>
                <Link className="btn btn-primary" to={`/notebooks/${notebookId}/chats/${chat.id}`}>
                  Continue
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="paper">
        <h2>Handoffs</h2>
        {handoffs.loading ? <p className="muted">Loading handoffs…</p> : null}
        {handoffs.error ? (
          <p className="muted">No handoff list yet ({errorMessage(handoffs.error)}).</p>
        ) : null}
        {!handoffs.loading && landing.length === 0 ? (
          <p className="empty">
            No specialist handoffs yet. Close a focus chat to land a summary here.
          </p>
        ) : null}
        {landing.map((handoff) => (
          <HandoffCard
            key={handoff.id || handoff.created_at}
            handoff={handoff}
            names={names}
            active={handoff.id === highlighted?.id}
          />
        ))}
      </section>

      <div className="row">
        {openSpecialists.length > 0 ? (
          <Link className="btn btn-primary" to={`/notebooks/${notebookId}/chats/${openSpecialists[0].id}`}>
            Continue focus chat
          </Link>
        ) : rows.length === 0 ? (
          <Link className="btn btn-primary" to={`/notebooks/${notebookId}/quiz`}>
            Start pretest
          </Link>
        ) : (
          <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/scoreboard`}>
            Back to scoreboard
          </Link>
        )}
      </div>
    </div>
  );
}

function topicLabel(chat: Chat, names: Map<string, string>): string {
  if (!chat.topic_ids.length) return "Specialist";
  return chat.topic_ids.map((id) => names.get(id) ?? id).join(", ");
}

function HandoffCard({
  handoff,
  names,
  active,
}: {
  handoff: Handoff;
  names: Map<string, string>;
  active: boolean;
}) {
  const topics = handoff.topic_ids.map((id) => names.get(id) ?? id).join(", ");
  return (
    <article className={`message message-handoff${active ? " message-active" : ""}`}>
      <p>
        <span className="badge badge-ok">Handoff</span>{" "}
        {topics ? <strong>{topics}</strong> : null}{" "}
        <span className="muted">{formatWhen(handoff.created_at)}</span>
      </p>
      <p>{handoff.summary}</p>
      {handoff.scoreboard_snapshot.length ? (
        <ul className="list">
          {handoff.scoreboard_snapshot.map((row: TopicScore) => (
            <li key={row.topic_id} className="muted">
              {row.name ?? names.get(row.topic_id) ?? row.topic_id}: {formatPercent(row.correct_rate)} ({row.severity})
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
