import { Link, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Topic, TopicScore } from "../api/types";
import { Banner } from "../components/Banner";
import { useAsync } from "../hooks/useAsync";
import { errorMessage, formatPercent } from "../lib/format";

type Ctx = { notebookId: string };

export function Scoreboard() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const board = useAsync(() => api.getScoreboard(notebookId), [api, notebookId]);
  const topics = useAsync(() => api.listTopics(notebookId), [api, notebookId]);

  const names = new Map((topics.data ?? []).map((t: Topic) => [t.id, t.name]));
  const rows = board.data?.topics ?? [];
  const bar = board.data?.proficiency_bar ?? 0.8;
  const windowSize = board.data?.window ?? 20;

  return (
    <div className="stack">
      <header>
        <h1>Scoreboard</h1>
        <p className="lede">
          Per-topic rates on the last {windowSize} attempts. Proficient at {formatPercent(bar)}.
        </p>
      </header>

      {board.error ? <Banner tone="error">{errorMessage(board.error)}</Banner> : null}
      {board.loading ? <p className="muted">Loading scoreboard…</p> : null}

      {!board.loading && rows.length === 0 ? (
        <Banner>
          No topic scores yet. Take a pretest so attempts can land here.{" "}
          <Link to={`/notebooks/${notebookId}/quiz`}>Start pretest</Link>
        </Banner>
      ) : null}

      {rows.map((row) => (
        <ScoreRow key={row.topic_id} row={row} name={row.name ?? names.get(row.topic_id) ?? row.topic_id} bar={bar} />
      ))}

      <div className="row">
        <Link className="btn btn-primary" to={`/notebooks/${notebookId}/quiz`}>
          Take another pretest
        </Link>
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/vault`}>
          Inspect vault
        </Link>
      </div>
    </div>
  );
}

function ScoreRow({ row, name, bar }: { row: TopicScore; name: string; bar: number }) {
  const width = Math.max(0, Math.min(100, Math.round(row.correct_rate * 100)));
  return (
    <article className="paper">
      <div className="list-row">
        <div>
          <h2>{name}</h2>
          <p className="muted">
            {row.correct_count}/{row.attempt_count} correct
            {row.attempt_count ? ` · ${formatPercent(row.correct_rate)}` : ""}
          </p>
        </div>
        <div className="row">
          <span className={`badge ${row.proficient ? "badge-ok" : "badge-pending"}`}>
            {row.proficient ? "Proficient" : `Below ${formatPercent(bar)}`}
          </span>
          <span className={`badge badge-${row.severity}`}>{row.severity}</span>
        </div>
      </div>
      <div
        className={`meter meter-mark meter-${row.severity}`}
        role="img"
        aria-label={`${formatPercent(row.correct_rate)} correct; bar at ${formatPercent(bar)}`}
      >
        <span style={{ width: `${width}%` }} />
      </div>
    </article>
  );
}
