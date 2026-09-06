import {
  PROFICIENCY_BAR,
  SCORE_WINDOW,
  SEVERE_MISS_COUNT,
  SEVERE_RATE,
  type Attempt,
  type Scoreboard,
  type Topic,
  type TopicScore,
} from "./types.js";

export function scoreTopic(
  notebookId: string,
  topicId: string,
  attempts: Attempt[],
  now = new Date().toISOString(),
): TopicScore {
  const windowed = attempts
    .filter((a) => a.topic_ids.includes(topicId))
    .slice(-SCORE_WINDOW);

  const attemptCount = windowed.length;
  const correctCount = windowed.filter((a) => a.correct).length;
  const missCount = attemptCount - correctCount;
  const correctRate = attemptCount === 0 ? 0 : correctCount / attemptCount;
  const proficient = attemptCount > 0 && correctRate >= PROFICIENCY_BAR;

  let severity: TopicScore["severity"] = "ok";
  if (attemptCount > 0) {
    if (correctRate < SEVERE_RATE || missCount >= SEVERE_MISS_COUNT) {
      severity = "severe";
    } else if (!proficient) {
      severity = "mild";
    }
  }

  return {
    topic_id: topicId,
    notebook_id: notebookId,
    correct_count: correctCount,
    attempt_count: attemptCount,
    correct_rate: correctRate,
    proficient,
    severity,
    updated_at: now,
  };
}

export function buildScoreboard(notebookId: string, topics: Topic[], attempts: Attempt[]): Scoreboard {
  const now = new Date().toISOString();
  return {
    topics: topics.map((topic) => scoreTopic(notebookId, topic.id, attempts, now)),
    window: SCORE_WINDOW,
    proficiency_bar: PROFICIENCY_BAR,
  };
}
