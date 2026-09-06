import { type AddressInfo } from "node:net";
import { afterEach, describe, expect, it } from "vitest";
import { StudyEngine } from "../src/engine.js";
import { StudyError } from "../src/errors.js";
import { createStudyServer } from "../src/http.js";
import { createFixtureVault, FIXTURE_NOTEBOOK_ID } from "../src/vault.js";

function engine(vault = createFixtureVault()) {
  return new StudyEngine({ vault });
}

describe("confirm gate", () => {
  it("refuses pretest generation until topics are confirmed", async () => {
    const study = engine();
    const proposed = await study.proposeTopics(FIXTURE_NOTEBOOK_ID);
    expect(proposed.length).toBeGreaterThan(0);
    expect(proposed.every((t) => t.confirmed === false)).toBe(true);

    await expect(study.createQuiz(FIXTURE_NOTEBOOK_ID)).rejects.toMatchObject({
      code: "TopicsUnconfirmed",
      status: 409,
    });
  });

  it("refuses when the notebook has no topics", async () => {
    const study = engine();
    await expect(study.createQuiz("missing")).rejects.toBeInstanceOf(StudyError);
    await expect(study.createQuiz("missing")).rejects.toMatchObject({
      code: "TopicsUnconfirmed",
      status: 409,
    });
  });

  it("allows quiz generation after confirm", async () => {
    const study = engine();
    await study.proposeTopics(FIXTURE_NOTEBOOK_ID);
    const confirmed = study.confirmTopics(FIXTURE_NOTEBOOK_ID);
    expect(confirmed.every((t) => t.confirmed)).toBe(true);

    const { quiz, items } = await study.createQuiz(FIXTURE_NOTEBOOK_ID);
    expect(quiz.kind).toBe("pretest");
    expect(quiz.notebook_id).toBe(FIXTURE_NOTEBOOK_ID);
    expect(items.length).toBeGreaterThan(0);
    expect(quiz.item_ids).toEqual(items.map((i) => i.id));
  });

  it("treats an explicit topic list as already confirmed (skip propose)", async () => {
    const study = engine();
    const topics = study.confirmTopics(FIXTURE_NOTEBOOK_ID, {
      names: ["Mitosis", "Meiosis"],
    });
    expect(topics).toHaveLength(2);
    expect(topics.every((t) => t.confirmed)).toBe(true);
    expect(topics.map((t) => t.name)).toEqual(["Mitosis", "Meiosis"]);

    const { items } = await study.createQuiz(FIXTURE_NOTEBOOK_ID);
    expect(items.length).toBeGreaterThan(0);
  });
});

describe("HTTP confirm gate", () => {
  const servers: { close(): Promise<void> }[] = [];

  afterEach(async () => {
    await Promise.all(servers.splice(0).map((s) => s.close()));
  });

  it("POST /notebooks/:id/quizzes returns 409 until confirm", async () => {
    const study = engine();
    const { base, close } = await listen(study);
    servers.push({ close });

    await fetchJson(base, "POST", `/notebooks/${FIXTURE_NOTEBOOK_ID}/topics/propose`);
    const refused = await fetchJson(base, "POST", `/notebooks/${FIXTURE_NOTEBOOK_ID}/quizzes`);
    expect(refused.status).toBe(409);
    expect(refused.body.error).toBe("TopicsUnconfirmed");

    await fetchJson(base, "POST", `/notebooks/${FIXTURE_NOTEBOOK_ID}/topics/confirm`);
    const ok = await fetchJson(base, "POST", `/notebooks/${FIXTURE_NOTEBOOK_ID}/quizzes`);
    expect(ok.status).toBe(200);
    expect(ok.body.quiz.kind).toBe("pretest");
    expect(ok.body.items.length).toBeGreaterThan(0);
  });
});

async function listen(study: StudyEngine) {
  const server = createStudyServer(study);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    base: `http://127.0.0.1:${port}`,
    close: () => new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve()))),
  };
}

async function fetchJson(base: string, method: string, path: string, body?: unknown) {
  const res = await fetch(`${base}${path}`, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> & { error?: string; quiz?: { kind: string }; items?: unknown[] } };
}
