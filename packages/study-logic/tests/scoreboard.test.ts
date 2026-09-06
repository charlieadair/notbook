import { describe, expect, it } from "vitest";
import { StudyEngine } from "../src/engine.js";
import { scoreTopic } from "../src/scoreboard.js";
import type { Attempt } from "../src/types.js";
import { PROFICIENCY_BAR, SCORE_WINDOW } from "../src/types.js";
import { createFixtureVault, FIXTURE_NOTEBOOK_ID } from "../src/vault.js";

function attempt(overrides: Partial<Attempt> & { topic_ids: string[] }): Attempt {
  return {
    id: overrides.id ?? crypto.randomUUID(),
    item_id: overrides.item_id ?? "item",
    quiz_id: overrides.quiz_id ?? "quiz",
    notebook_id: overrides.notebook_id ?? "nb",
    selected_choice_id: overrides.selected_choice_id ?? "c",
    correct: overrides.correct ?? false,
    topic_ids: overrides.topic_ids,
    created_at: overrides.created_at ?? new Date().toISOString(),
  };
}

describe("scoreboard", () => {
  it("updates topic scores when an attempt is graded", async () => {
    const study = new StudyEngine({ vault: createFixtureVault() });
    study.confirmTopics(FIXTURE_NOTEBOOK_ID, { names: ["Mitosis"] });
    const { quiz, items } = await study.createQuiz(FIXTURE_NOTEBOOK_ID);
    const item = items[0];

    const result = study.gradeAttempt(quiz.id, {
      item_id: item.id,
      selected_choice_id: item.correct_choice_id,
    });
    expect(result.attempt.correct).toBe(true);
    expect(result.scores[0].attempt_count).toBe(1);
    expect(result.scores[0].correct_count).toBe(1);
    expect(result.scores[0].correct_rate).toBe(1);

    const board = study.scoreboard(FIXTURE_NOTEBOOK_ID);
    expect(board.window).toBe(SCORE_WINDOW);
    expect(board.proficiency_bar).toBe(PROFICIENCY_BAR);
    expect(board.topics[0].attempt_count).toBe(1);
    expect(board.topics[0].proficient).toBe(true);
    expect(board.topics[0].severity).toBe("ok");
  });

  it("uses the last 20 attempts per topic", () => {
    const topicId = "t1";
    const attempts = [
      ...Array.from({ length: 5 }, (_, i) =>
        attempt({ id: `old-${i}`, correct: false, topic_ids: [topicId] }),
      ),
      ...Array.from({ length: 20 }, (_, i) =>
        attempt({ id: `new-${i}`, correct: true, topic_ids: [topicId] }),
      ),
    ];
    const score = scoreTopic("nb", topicId, attempts);
    expect(score.attempt_count).toBe(20);
    expect(score.correct_count).toBe(20);
    expect(score.correct_rate).toBe(1);
    expect(score.proficient).toBe(true);
  });

  it("marks severe when rate < 0.5 or there are at least 3 misses", () => {
    const lowRate = scoreTopic(
      "nb",
      "t1",
      Array.from({ length: 4 }, (_, i) =>
        attempt({ id: `l${i}`, correct: i === 0, topic_ids: ["t1"] }),
      ),
    );
    expect(lowRate.correct_rate).toBe(0.25);
    expect(lowRate.severity).toBe("severe");
    expect(lowRate.proficient).toBe(false);

    const threeMisses = scoreTopic(
      "nb",
      "t1",
      [
        ...Array.from({ length: 17 }, (_, i) =>
          attempt({ id: `ok${i}`, correct: true, topic_ids: ["t1"] }),
        ),
        ...Array.from({ length: 3 }, (_, i) =>
          attempt({ id: `miss${i}`, correct: false, topic_ids: ["t1"] }),
        ),
      ],
    );
    expect(threeMisses.correct_rate).toBe(0.85);
    expect(threeMisses.proficient).toBe(true);
    expect(threeMisses.severity).toBe("severe");
  });
});
