import { useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { useApi } from "../api/ApiContext";
import type { Topic } from "../api/types";
import { Banner } from "../components/Banner";
import { ScoreRow } from "../components/ScoreRow";
import { SpawnOfferPanel } from "../components/SpawnOfferPanel";
import { useAsync } from "../hooks/useAsync";
import { errorMessage, formatPercent } from "../lib/format";

type Ctx = { notebookId: string };

export function Scoreboard() {
  const { notebookId } = useOutletContext<Ctx>();
  const api = useApi();
  const board = useAsync(() => api.getScoreboard(notebookId), [api, notebookId]);
  const topics = useAsync(() => api.listTopics(notebookId), [api, notebookId]);
  const [hasOffer, setHasOffer] = useState(false);

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

      {!board.loading && rows.length > 0 ? (
        <SpawnOfferPanel notebookId={notebookId} onAvailability={setHasOffer} />
      ) : null}

      <div className="row">
        <Link
          className={hasOffer ? "btn btn-ghost" : "btn btn-primary"}
          to={`/notebooks/${notebookId}/quiz`}
        >
          Take another pretest
        </Link>
        <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/vault`}>
          Inspect vault
        </Link>
        {rows.length > 0 ? (
          <Link className="btn btn-ghost" to={`/notebooks/${notebookId}/orchestrator`}>
            Orchestrator
          </Link>
        ) : null}
      </div>
    </div>
  );
}
