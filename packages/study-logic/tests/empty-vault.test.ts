import { describe, expect, it } from "vitest";
import { StudyEngine } from "../src/engine.js";
import { InMemoryVault } from "../src/vault.js";

describe("empty vault", () => {
  it("does not invent items when the vault is empty", async () => {
    const study = new StudyEngine({ vault: new InMemoryVault() });
    study.confirmTopics("nb_empty", { names: ["Mitosis"] });

    await expect(study.createQuiz("nb_empty")).rejects.toMatchObject({
      code: "InsufficientEvidence",
      status: 422,
    });
  });

  it("does not invent items when retrieve returns no citable chunks", async () => {
    const vault = new InMemoryVault({
      nb_blank: [
        {
          id: "chunk_blank",
          source_id: "blank",
          text: "   ",
          locator: "blank.md",
          score: 0,
          source_filename: "blank.md",
        },
      ],
    });
    const study = new StudyEngine({ vault });
    study.confirmTopics("nb_blank", { names: ["Anything"] });

    await expect(study.createQuiz("nb_blank")).rejects.toMatchObject({
      code: "InsufficientEvidence",
      status: 422,
    });
  });

  it("propose from an empty vault returns no topics rather than invented names", async () => {
    const study = new StudyEngine({ vault: new InMemoryVault() });
    const topics = await study.proposeTopics("nb_empty");
    expect(topics).toEqual([]);
  });
});
