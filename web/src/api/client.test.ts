import { describe, expect, it, vi } from "vitest";
import { HttpStudyApi } from "./client";
import { ApiError } from "./errors";
import { MockStudyApi } from "./mock";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("HttpStudyApi.createPretest", () => {
  it("POSTs /notebooks/:id/quizzes only", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url).toBe("http://127.0.0.1:8000/api/v1/notebooks/nb/quizzes");
      return jsonResponse(200, {
        quiz: { id: "q1", notebook_id: "nb", kind: "pretest", item_ids: ["i1"], created_at: "t" },
        items: [
          {
            id: "i1",
            quiz_id: "q1",
            stem: "Stem",
            choices: [{ id: "c", text: "A" }],
            citation_chunk_ids: ["chk"],
          },
        ],
      });
    });

    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    const quiz = await api.createPretest("nb");
    expect(quiz.quiz.id).toBe("q1");
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("does not swallow a 409 topics gate", async () => {
    const fetchFn = vi.fn(async () =>
      jsonResponse(409, { error: "topics_unconfirmed", message: "Confirm every topic" }),
    );
    const api = new HttpStudyApi({ baseUrl: "/api/v1", fetchFn });
    await expect(api.createPretest("nb")).rejects.toMatchObject({
      status: 409,
      isTopicsUnconfirmed: true,
    });
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("uploads and pastes via POST /notebooks/:id/sources only", async () => {
    const urls: string[] = [];
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      urls.push(String(input));
      return jsonResponse(201, { id: "s1", filename: "a.pdf", extract_status: "ok", chunk_count: 1 });
    });
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    await api.uploadSource("nb", new File(["x"], "a.pdf"));
    await api.pasteSource("nb", { text: "hello there this is pasted notes." });
    expect(urls).toEqual([
      "http://127.0.0.1:8000/api/v1/notebooks/nb/sources",
      "http://127.0.0.1:8000/api/v1/notebooks/nb/sources",
    ]);
  });

  it("lists chunks at GET /sources/:id/chunks", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://127.0.0.1:8000/api/v1/sources/src1/chunks");
      return jsonResponse(200, [{ id: "c1", text: "chunk" }]);
    });
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    const chunks = await api.listChunks("nb", "src1");
    expect(chunks[0].id).toBe("c1");
  });
});

describe("MockStudyApi S0 path", () => {
  it("gates pretest until confirm and requires chunks", async () => {
    const api = new MockStudyApi();
    const nb = await api.createNotebook("Bio");
    await expect(api.createPretest(nb.id)).rejects.toBeInstanceOf(ApiError);

    await api.proposeTopics(nb.id);
    await expect(api.createPretest(nb.id)).rejects.toMatchObject({ isTopicsUnconfirmed: true });

    await api.confirmTopics(nb.id);
    await expect(api.createPretest(nb.id)).rejects.toMatchObject({ isInsufficientEvidence: true });

    await api.pasteSource(nb.id, {
      text: "Mitosis produces two identical daughter cells. Meiosis produces gametes with half the chromosomes.",
    });
    const proposed = await api.proposeTopics(nb.id);
    await api.confirmTopics(nb.id, { topic_ids: proposed.map((t) => t.id) });
    const quiz = await api.createPretest(nb.id);
    expect(quiz.items.every((item) => item.citation_chunk_ids.length > 0)).toBe(true);

    const first = quiz.items[0];
    await api.submitAttempt(quiz.quiz.id, {
      item_id: first.id,
      selected_choice_id: first.choices[0].id,
    });
    const board = await api.getScoreboard(nb.id);
    expect(board.window).toBe(20);
    expect(board.proficiency_bar).toBe(0.8);
    expect(board.topics.length).toBeGreaterThan(0);
  });

  it("marks extract failed when the filename includes fail", async () => {
    const api = new MockStudyApi();
    const nb = await api.createNotebook("Scan");
    const source = await api.uploadSource(nb.id, new File(["x"], "notes-fail.png", { type: "image/png" }));
    expect(source.extract_status).toBe("failed");
    expect(source.chunk_count).toBe(0);
  });
});
