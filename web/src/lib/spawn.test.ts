import { describe, expect, it } from "vitest";
import type { SpawnCandidate, TopicScore } from "../api/types";
import { capSpawnSelection, defaultSelectedTopicIds, offerFromScoreboard, sortSpawnCandidates } from "./spawn";

describe("spawn offer helpers", () => {
  it("defaults to at most 2 severe-first topic ids", () => {
    const candidates: SpawnCandidate[] = [
      { topic_id: "mild-a", severity: "mild", reason: "a" },
      { topic_id: "sev-b", severity: "severe", reason: "b" },
      { topic_id: "sev-c", severity: "severe", reason: "c" },
    ];
    expect(defaultSelectedTopicIds(candidates, 2)).toEqual(["sev-b", "sev-c"]);
    expect(sortSpawnCandidates(candidates).map((c) => c.topic_id)).toEqual(["sev-b", "sev-c", "mild-a"]);
  });

  it("caps a user selection at max_spawn without duplicates", () => {
    expect(capSpawnSelection(["t1", "t1", "t2", "t3"], 2)).toEqual(["t1", "t2"]);
  });

  it("builds an offer from scoreboard without hiding mild on the board", () => {
    const scores: TopicScore[] = [
      score("ok-1", "ok"),
      score("mild-1", "mild"),
      score("sev-1", "severe"),
      score("sev-2", "severe"),
      score("sev-3", "severe"),
    ];
    const offer = offerFromScoreboard("nb", scores, 2);
    expect(offer.max_spawn).toBe(2);
    expect(offer.candidates).toHaveLength(2);
    expect(offer.candidates.every((c) => c.severity === "severe")).toBe(true);
    expect(scores.filter((s) => s.severity === "mild")).toHaveLength(1);
  });
});

function score(topicId: string, severity: TopicScore["severity"]): TopicScore {
  return {
    topic_id: topicId,
    notebook_id: "nb",
    correct_count: severity === "ok" ? 8 : 1,
    attempt_count: 10,
    correct_rate: severity === "ok" ? 0.8 : severity === "mild" ? 0.6 : 0.2,
    proficient: severity === "ok",
    severity,
    updated_at: "now",
    name: topicId,
  };
}
