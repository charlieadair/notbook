import { describe, expect, it } from "vitest";
import { proposeTopicNames } from "../src/topics.js";
import { fixtureChunks } from "../src/vault.js";
import type { Chunk } from "../src/types.js";

function chunk(text: string, filename = "lecture.txt"): Chunk {
  return {
    id: "chunk_1",
    source_id: "src",
    text,
    locator: "lecture.txt",
    score: 1,
    source_filename: filename,
  };
}

describe("proposeTopicNames", () => {
  it("rejects This is… and keeps a real term like Mitosis", () => {
    const names = proposeTopicNames([chunk("This is a lemma. Mitosis is cell division.")]);
    const lowered = names.map((name) => name.toLowerCase());
    expect(lowered).not.toContain("this");
    expect(names.some((name) => name.toLowerCase().includes("mitosis"))).toBe(true);
  });

  it("does not yield What from What is energy?", () => {
    const names = proposeTopicNames([chunk("What is energy?")]);
    expect(names.map((name) => name.toLowerCase())).not.toContain("what");
  });

  it("keeps headings and sensible source stems", () => {
    const names = proposeTopicNames([
      chunk("# Breadth-first search\nThis is an overview of the algorithm.", "Algorithms Test.pdf"),
    ]);
    expect(names).toContain("Breadth-first search");
    expect(names).toContain("Algorithms Test");
    expect(names).not.toContain("This");
  });

  it("still proposes fixture vault topics", () => {
    const names = proposeTopicNames(fixtureChunks());
    expect(names).toEqual(expect.arrayContaining(["Mitosis", "Meiosis", "Photosynthesis"]));
    expect(names).not.toContain("This");
    expect(names).not.toContain("What");
  });
});
