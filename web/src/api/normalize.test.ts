import { describe, expect, it } from "vitest";
import { ApiError, parseErrorBody } from "./errors";
import {
  toChat,
  toChats,
  toChunk,
  toGeneratedQuiz,
  toGradeAttemptResult,
  toHandoff,
  toHandoffs,
  toHealth,
  toNotebooks,
  toScoreboard,
  toSource,
  toSpawnOffer,
  toTopics,
} from "./normalize";

describe("normalize", () => {
  it("unwraps notebook lists from several envelopes", () => {
    expect(toNotebooks([{ id: "a", title: "Bio" }])).toEqual([
      { id: "a", title: "Bio", created_at: undefined },
    ]);
    expect(toNotebooks({ notebooks: [{ id: "b", name: "Chem" }] })[0].title).toBe("Chem");
  });

  it("maps extract status aliases onto ok | failed | pending", () => {
    expect(toSource({ id: "1", filename: "a.pdf", extract_status: "success", chunk_count: 3 }).extract_status).toBe(
      "ok",
    );
    expect(toSource({ id: "2", filename: "b.png", status: "ocr_failed" }).extract_status).toBe("failed");
    expect(toSource({ id: "3", filename: "c.md", extract_status: "processing" }).extract_status).toBe("pending");
  });

  it("reads topics from a { topics } envelope", () => {
    const topics = toTopics({
      topics: [{ id: "t1", notebook_id: "n", name: "Mitosis", confirmed: true, sort_order: 0 }],
    });
    expect(topics).toHaveLength(1);
    expect(topics[0].confirmed).toBe(true);
  });

  it("accepts quiz + items or a flat quiz object", () => {
    const wrapped = toGeneratedQuiz({
      quiz: { id: "q1", notebook_id: "n", kind: "pretest", item_ids: ["i1"], created_at: "t" },
      items: [
        {
          id: "i1",
          quiz_id: "q1",
          stem: "Why?",
          choices: [{ id: "c1", text: "A" }],
          citation_chunk_ids: ["chk1"],
        },
      ],
    });
    expect(wrapped.quiz.id).toBe("q1");
    expect(wrapped.items[0].citation_chunk_ids).toEqual(["chk1"]);

    const flat = toGeneratedQuiz({
      id: "q2",
      notebook_id: "n",
      items: [{ id: "i2", question: "What?", options: ["Yes"], citation_chunk_ids: ["chk2"] }],
    });
    expect(flat.quiz.id).toBe("q2");
    expect(flat.items[0].stem).toBe("What?");
    expect(flat.items[0].choices[0].text).toBe("Yes");
  });

  it("maps Backend health {status:ok} and nested chunk.source", () => {
    expect(toHealth({ status: "ok", service: "notbook-study-api" })).toEqual({
      ok: true,
      service: "notbook-study-api",
    });
    const chunk = toChunk({
      id: "c1",
      text: "hello",
      source: { filename: "notes.pdf" },
      locator: { page: 2 },
    });
    expect(chunk.source_label).toBe("notes.pdf");
  });

  it("reads locked attempt + scoreboard envelopes", () => {
    const graded = toGradeAttemptResult({
      attempt: { id: "a", item_id: "i", quiz_id: "q", notebook_id: "n", selected_choice_id: "c", correct: true, topic_ids: ["t"], created_at: "now" },
      scoreboard: {
        topics: [{ topic_id: "t", notebook_id: "n", correct_count: 1, attempt_count: 2, correct_rate: 0.5, proficient: false, severity: "mild", updated_at: "now" }],
        window: 20,
        proficiency_bar: 0.8,
      },
    });
    expect(graded.attempt.correct).toBe(true);
    expect(graded.scoreboard.topics[0].severity).toBe("mild");
    expect(graded.scoreboard.window).toBe(20);
    expect(graded.scoreboard.proficiency_bar).toBe(0.8);

    const board = toScoreboard({
      topics: [{ topic_id: "t", correct_rate: 1, proficient: true, severity: "ok" }],
      window: 20,
      proficiency_bar: 0.8,
    });
    expect(board.window).toBe(20);
    expect(board.proficiency_bar).toBe(0.8);
  });
});

describe("S1 chat-tree normalize", () => {
  it("reads spawn-offer envelopes from issue #22", () => {
    const offer = toSpawnOffer(
      {
        notebook_id: "nb",
        candidates: [
          { topic_id: "t1", severity: "severe", reason: "5 misses" },
          { topic_id: "t2", severity: "mild", reason: "2 misses" },
        ],
        max_spawn: 2,
      },
      "nb",
    );
    expect(offer.candidates).toHaveLength(2);
    expect(offer.max_spawn).toBe(2);
    expect(toSpawnOffer({ offer: { candidates: [{ id: "x", severity: "severe" }], max_spawn: 2 } }).candidates[0].topic_id).toBe(
      "x",
    );
  });

  it("reads chat, specialist list, and handoff wrappers", () => {
    const chat = toChat({
      chat: { id: "c1", notebook_id: "nb", kind: "specialist", topic_ids: ["t1"], status: "open", created_at: "now" },
    });
    expect(chat.kind).toBe("specialist");
    expect(toChats({ chats: [chat] })).toHaveLength(1);
    const handoff = toHandoff({
      handoff: {
        id: "h1",
        from_chat_id: "c1",
        to_chat_id: "orch",
        topic_ids: ["t1"],
        summary: "Back from eigenvalues",
        scoreboard_snapshot: [{ topic_id: "t1", correct_rate: 0.4, severity: "severe" }],
        created_at: "now",
      },
    });
    expect(handoff.summary).toMatch(/eigenvalues/);
    expect(handoff.scoreboard_snapshot[0].severity).toBe("severe");
    expect(toHandoffs({ handoffs: [handoff] })).toHaveLength(1);
  });
});

describe("ApiError", () => {
  it("classifies 409 topics_unconfirmed and 422 insufficient_evidence", () => {
    const gate = new ApiError(409, "topics_unconfirmed", "confirm first");
    const thin = new ApiError(422, "insufficient_evidence", "no chunks");
    expect(gate.isTopicsUnconfirmed).toBe(true);
    expect(thin.isInsufficientEvidence).toBe(true);
    expect(new ApiError(404, "NotFound", "missing").isUnavailable).toBe(true);
    expect(parseErrorBody({ error: "topics_unconfirmed" }).code).toBe("topics_unconfirmed");
    expect(parseErrorBody({ error: "insufficient_evidence" }).code).toBe("insufficient_evidence");
  });
});
