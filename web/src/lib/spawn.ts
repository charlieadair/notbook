import { DEFAULT_MAX_SPAWN, type SpawnCandidate, type SpawnOffer, type TopicScore } from "../api/types";

const SEVERITY_RANK: Record<string, number> = { severe: 0, mild: 1 };

export function emptySpawnOffer(notebookId: string): SpawnOffer {
  return { notebook_id: notebookId, candidates: [], max_spawn: DEFAULT_MAX_SPAWN };
}

export function sortSpawnCandidates(candidates: SpawnCandidate[]): SpawnCandidate[] {
  return [...candidates].sort((a, b) => {
    const rank = (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
    return rank !== 0 ? rank : a.topic_id.localeCompare(b.topic_id);
  });
}

/** Default suggest at most `max_spawn` (SPEC: 2), severe-first. */
export function defaultSelectedTopicIds(
  candidates: SpawnCandidate[],
  maxSpawn = DEFAULT_MAX_SPAWN,
): string[] {
  return sortSpawnCandidates(candidates)
    .slice(0, Math.max(0, maxSpawn))
    .map((c) => c.topic_id);
}

export function capSpawnSelection(topicIds: string[], maxSpawn = DEFAULT_MAX_SPAWN): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of topicIds) {
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
    if (out.length >= maxSpawn) break;
  }
  return out;
}

/** Client helper for mock / tests. Mild stays on the scoreboard even if not offered. */
export function offerFromScoreboard(notebookId: string, scores: TopicScore[], maxSpawn = DEFAULT_MAX_SPAWN): SpawnOffer {
  const candidates = sortSpawnCandidates(
    scores
      .filter((row) => row.severity === "severe" || row.severity === "mild")
      .map((row) => ({
        topic_id: row.topic_id,
        severity: row.severity as SpawnCandidate["severity"],
        reason:
          row.severity === "severe"
            ? `Severe gap: ${row.correct_count}/${row.attempt_count} correct on recent items.`
            : `Mild gap still visible: ${row.correct_count}/${row.attempt_count} correct — do not hide it.`,
      })),
  ).slice(0, maxSpawn);
  return { notebook_id: notebookId, candidates, max_spawn: maxSpawn };
}
