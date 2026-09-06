import { describe, expect, it } from "vitest";
import { StudyEngine } from "../src/engine.js";
import { MAX_CHOICE_CHARS, SOURCE_RECALL_PHRASE, buildGroundedItems } from "../src/quiz.js";
import type { Chunk } from "../src/types.js";
import { InMemoryVault, createFixtureVault, FIXTURE_NOTEBOOK_ID } from "../src/vault.js";

const bigO: Chunk = {
  id: "chunk_bigo",
  source_id: "notes-bigo",
  text: "Big-O describes an upper bound on the growth of a function.",
  locator: "lecture-bigo.md#big-o",
  score: 1,
  source_filename: "lecture-bigo.md",
};

describe("exam-shaped quiz items", () => {
  it("fixture pretest stems are conceptual, not source-matching", async () => {
    const study = new StudyEngine({ vault: createFixtureVault() });
    study.confirmTopics(FIXTURE_NOTEBOOK_ID, { names: ["Mitosis", "Photosynthesis"] });
    const { items } = await study.createQuiz(FIXTURE_NOTEBOOK_ID);
    expect(items.length).toBeGreaterThan(0);
    for (const item of items) {
      expect(item.stem.toLowerCase()).not.toContain(SOURCE_RECALL_PHRASE);
      const correct = item.choices.find((c) => c.id === item.correct_choice_id);
      expect(correct!.text.length).toBeLessThanOrEqual(MAX_CHOICE_CHARS);
      expect(item.citation_chunk_ids.length).toBeGreaterThan(0);
      expect(item.rationale?.toLowerCase()).toContain("because [");
    }
  });

  it("turns a Big-O definition into a meaning question with a short choice", async () => {
    const study = new StudyEngine({ vault: new InMemoryVault({ nb_algo: [bigO] }) });
    study.confirmTopics("nb_algo", { names: ["Big-O"] });
    const { items } = await study.createQuiz("nb_algo");
    expect(items.length).toBeGreaterThan(0);
    const item = items[0];
    expect(item.stem.toLowerCase()).toContain("what does");
    expect(item.stem.toLowerCase()).toContain("describe");
    expect(item.stem.toLowerCase()).not.toContain(SOURCE_RECALL_PHRASE);
    const correct = item.choices.find((c) => c.id === item.correct_choice_id);
    expect(correct!.text.toLowerCase()).toContain("upper bound");
    expect(correct!.text.length).toBeLessThanOrEqual(MAX_CHOICE_CHARS);
    expect(item.citation_chunk_ids).toEqual(["chunk_bigo"]);
  });

  it("drops a long OCR blob that cannot be turned into a short concept", () => {
    const blob = `Big-O lecture notes ${"garbled slide token ".repeat(20)}`.trim();
    const items = buildGroundedItems({
      quizId: "q1",
      topics: [{ id: "t1", notebook_id: "nb", name: "Big-O", confirmed: true, sort_order: 0 }],
      evidence: new Map([
        [
          "t1",
          [
            {
              id: "chunk_ocr",
              source_id: "ocr",
              text: blob,
              locator: "ocr.md",
              score: 1,
              source_filename: "ocr.md",
            },
          ],
        ],
      ]),
    });
    expect(items).toEqual([]);
  });
});
