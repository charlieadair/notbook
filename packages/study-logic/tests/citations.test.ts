import { describe, expect, it } from "vitest";
import { StudyEngine } from "../src/engine.js";
import { isGroundedItem, keepGroundedItems } from "../src/quiz.js";
import type { QuizItem } from "../src/types.js";
import { createFixtureVault, fixtureChunks, FIXTURE_NOTEBOOK_ID } from "../src/vault.js";

describe("citation required", () => {
  it("generated items always have citation_chunk_ids pointing at retrieved chunks", async () => {
    const vault = createFixtureVault();
    const study = new StudyEngine({ vault });
    study.confirmTopics(FIXTURE_NOTEBOOK_ID, { names: ["Mitosis", "Photosynthesis"] });
    const { items } = await study.createQuiz(FIXTURE_NOTEBOOK_ID);
    const known = new Set(fixtureChunks().map((c) => c.id));

    expect(items.length).toBeGreaterThan(0);
    for (const item of items) {
      expect(item.citation_chunk_ids.length).toBeGreaterThan(0);
      expect(isGroundedItem(item, known)).toBe(true);
      for (const id of item.citation_chunk_ids) {
        const chunk = vault.getChunk(id);
        expect(chunk).toBeDefined();
        expect(chunk!.text.trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("drops uncited items", () => {
    const known = new Set(["chunk_mitosis"]);
    const cited: QuizItem = {
      id: "i1",
      quiz_id: "q1",
      topic_ids: ["t1"],
      stem: "grounded",
      choices: [{ id: "a", text: "from source" }],
      correct_choice_id: "a",
      citation_chunk_ids: ["chunk_mitosis"],
    };
    const uncited: QuizItem = {
      id: "i2",
      quiz_id: "q1",
      topic_ids: ["t1"],
      stem: "invented",
      choices: [{ id: "b", text: "not in vault" }],
      correct_choice_id: "b",
      citation_chunk_ids: [],
    };
    const unknownCite: QuizItem = {
      id: "i3",
      quiz_id: "q1",
      topic_ids: ["t1"],
      stem: "fake cite",
      choices: [{ id: "c", text: "ghost" }],
      correct_choice_id: "c",
      citation_chunk_ids: ["chunk_missing"],
    };

    const kept = keepGroundedItems([cited, uncited, unknownCite], known);
    expect(kept.map((i) => i.id)).toEqual(["i1"]);
  });
});
