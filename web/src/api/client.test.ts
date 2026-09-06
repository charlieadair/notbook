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

describe("HttpStudyApi OpenAPI vault paths", () => {
  it("GETs /health and maps HealthOut {status, service}", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://127.0.0.1:8000/api/v1/health");
      return jsonResponse(200, { status: "ok", service: "notbook-study-api" });
    });
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    await expect(api.health()).resolves.toEqual({ ok: true, service: "notbook-study-api" });
  });
});

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

  it("parses locked Study-logic JSON envelopes", async () => {
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/topics/propose")) {
        return jsonResponse(200, {
          topics: [{ id: "t1", notebook_id: "nb", name: "Mitosis", confirmed: false, sort_order: 0 }],
        });
      }
      if (url.endsWith("/attempts")) {
        return jsonResponse(200, {
          attempt: {
            id: "a1",
            item_id: "i1",
            quiz_id: "q1",
            notebook_id: "nb",
            selected_choice_id: "c1",
            correct: true,
            topic_ids: ["t1"],
            created_at: "now",
          },
          scoreboard: { topics: [{ topic_id: "t1", notebook_id: "nb", correct_count: 1, attempt_count: 1, correct_rate: 1, proficient: true, severity: "ok", updated_at: "now" }], window: 20, proficiency_bar: 0.8 },
        });
      }
      return jsonResponse(500, { error: "unexpected" });
    });
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    const topics = await api.proposeTopics("nb");
    expect(topics[0]).toMatchObject({ id: "t1", confirmed: false, sort_order: 0 });
    const graded = await api.submitAttempt("q1", { item_id: "i1", selected_choice_id: "c1" });
    expect(graded.scoreboard.window).toBe(20);
    expect(graded.scoreboard.proficiency_bar).toBe(0.8);
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

describe("HttpStudyApi S1 stubs", () => {
  it("GETs spawn-offer / chats / handoffs and POSTs specialists + close", async () => {
    const urls: string[] = [];
    const fetchFn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      urls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.endsWith("/spawn-offer")) {
        return jsonResponse(200, {
          candidates: [{ topic_id: "t1", severity: "severe", reason: "5 misses" }],
          max_spawn: 2,
        });
      }
      if (url.endsWith("/chats/specialists")) {
        return jsonResponse(200, {
          chat: { id: "c1", notebook_id: "nb", kind: "specialist", topic_ids: ["t1"], status: "open", created_at: "t", closed_at: null },
          warnings: [],
        });
      }
      if (url.endsWith("/chats/orchestrator")) {
        return jsonResponse(200, {
          id: "orch",
          notebook_id: "nb",
          kind: "orchestrator",
          topic_ids: [],
          status: "open",
          created_at: "t",
          closed_at: null,
        });
      }
      if (url.endsWith("/chats")) {
        return jsonResponse(200, { chats: [] });
      }
      if (url.endsWith("/close")) {
        return jsonResponse(200, {
          chat: { id: "c1", notebook_id: "nb", kind: "specialist", topic_ids: ["t1"], status: "closed", created_at: "t", closed_at: "t" },
          handoff: {
            id: "h1",
            from_chat_id: "c1",
            to_chat_id: "orch",
            topic_ids: ["t1"],
            summary: "Done",
            scoreboard_snapshot: [],
            created_at: "t",
          },
        });
      }
      if (url.endsWith("/handoffs")) {
        return jsonResponse(200, { handoffs: [] });
      }
      return jsonResponse(500, { error: "unexpected" });
    });
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    const offer = await api.getSpawnOffer("nb");
    expect(offer.candidates[0].topic_id).toBe("t1");
    expect(offer.max_spawn).toBe(2);
    const created = await api.createSpecialists("nb", ["t1"]);
    expect(created.chats[0].id).toBe("c1");
    expect(created.warnings).toEqual([]);
    const handoff = await api.closeChat("c1");
    expect(handoff.summary).toBe("Done");
    await api.listChats("nb");
    await api.listHandoffs("nb");
    await api.getOrCreateOrchestrator("nb");
    expect(urls).toEqual([
      "GET http://127.0.0.1:8000/api/v1/notebooks/nb/spawn-offer",
      "POST http://127.0.0.1:8000/api/v1/notebooks/nb/chats/specialists",
      "POST http://127.0.0.1:8000/api/v1/chats/c1/close",
      "GET http://127.0.0.1:8000/api/v1/notebooks/nb/chats",
      "GET http://127.0.0.1:8000/api/v1/notebooks/nb/handoffs",
      "GET http://127.0.0.1:8000/api/v1/notebooks/nb/chats/orchestrator",
    ]);
  });

  it("returns empty S1 reads on 404 so the S0 spine stays usable", async () => {
    const fetchFn = vi.fn(async () => jsonResponse(404, { error: "NotFound" }));
    const api = new HttpStudyApi({ baseUrl: "http://127.0.0.1:8000/api/v1", fetchFn });
    await expect(api.getSpawnOffer("nb")).resolves.toEqual({
      notebook_id: "nb",
      candidates: [],
      max_spawn: 2,
    });
    await expect(api.listChats("nb")).resolves.toEqual([]);
    await expect(api.listHandoffs("nb")).resolves.toEqual([]);
    await expect(api.listChatMessages("c1")).resolves.toEqual([]);
    await expect(api.getOrCreateOrchestrator("nb")).resolves.toBeNull();
    await expect(api.getChat("c1")).resolves.toBeNull();
    await expect(api.sendChatMessage("c1", { text: "hi" })).resolves.toEqual({ message: null });
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

  it("runs S1 offer → specialist → close handoff without breaking the scoreboard", async () => {
    const api = new MockStudyApi();
    const nb = await api.createNotebook("LinAlg");
    await api.pasteSource(nb.id, {
      text: "Eigenvalues solve Av = λv for nonzero v. Linear regression minimizes squared residual error.",
    });
    const proposed = await api.proposeTopics(nb.id);
    await api.confirmTopics(nb.id, { topic_ids: proposed.map((t) => t.id) });
    const quiz = await api.createPretest(nb.id);
    for (const item of quiz.items) {
      const wrong = item.choices.find((c) => c.id !== item.correct_choice_id)?.id ?? item.choices[0].id;
      await api.submitAttempt(quiz.quiz.id, { item_id: item.id, selected_choice_id: wrong });
    }
    const before = await api.getScoreboard(nb.id);
    expect(before.topics.length).toBeGreaterThan(0);

    const offer = await api.getSpawnOffer(nb.id);
    expect(offer.max_spawn).toBe(2);
    expect(offer.candidates.length).toBeGreaterThan(0);
    expect(offer.candidates.length).toBeLessThanOrEqual(2);

    const specialists = await api.createSpecialists(
      nb.id,
      offer.candidates.map((c) => c.topic_id),
    );
    expect(specialists.chats).toHaveLength(1);
    expect(specialists.chats[0].kind).toBe("specialist");
    expect(specialists.chats[0].topic_ids.length).toBeGreaterThan(0);

    await api.sendChatMessage(specialists.chats[0].id, { text: "Stay on this topic." });
    const handoff = await api.closeChat(specialists.chats[0].id);
    expect(handoff.summary.length).toBeGreaterThan(0);
    expect(handoff.topic_ids).toEqual(specialists.chats[0].topic_ids);
    const landed = await api.listHandoffs(nb.id);
    expect(landed.some((h) => h.id === handoff.id)).toBe(true);
    const orch = await api.getOrCreateOrchestrator(nb.id);
    expect(orch?.kind).toBe("orchestrator");
    expect(handoff.to_chat_id).toBe(orch?.id);

    const after = await api.getScoreboard(nb.id);
    expect(after.window).toBe(20);
    expect(after.topics.length).toBe(before.topics.length);

    const firstOpen = await api.createSpecialists(nb.id, [offer.candidates[0].topic_id]);
    const secondOpen = await api.createSpecialists(nb.id, [offer.candidates[0].topic_id]);
    expect(firstOpen.chats).toHaveLength(1);
    expect(secondOpen.chats).toHaveLength(1);
    await expect(api.createSpecialists(nb.id, [offer.candidates[0].topic_id])).rejects.toMatchObject({
      status: 409,
      isTooManySpecialists: true,
    });
  });

  it("marks extract failed when the filename includes fail", async () => {
    const api = new MockStudyApi();
    const nb = await api.createNotebook("Scan");
    const source = await api.uploadSource(nb.id, new File(["x"], "notes-fail.png", { type: "image/png" }));
    expect(source.extract_status).toBe("failed");
    expect(source.chunk_count).toBe(0);
  });
});
