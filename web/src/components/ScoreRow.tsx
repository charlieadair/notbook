import type { TopicScore } from "../api/types";
import { formatPercent } from "../lib/format";

export function ScoreRow({ row, name, bar }: { row: TopicScore; name: string; bar: number }) {
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
