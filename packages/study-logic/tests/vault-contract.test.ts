import { describe, expect, it, vi } from "vitest";
import { DEFAULT_TOP_K } from "../src/types.js";
import { createFixtureVault, fixtureChunks, HttpVaultRetrieve, InMemoryVault } from "../src/vault.js";

const REQUIRED_FIELDS = ["id", "source_id", "text", "locator", "score", "source_filename"] as const;

describe("VaultRetrieve contract", () => {
  it("fixture retrieve returns Backend Chunk shape inside { chunks }", async () => {
    const vault = createFixtureVault();
    const envelope = await vault.retrieveEnvelope({
      notebook_id: "nb_bio",
      query: "Mitosis",
      top_k: 8,
    });
    expect(Array.isArray(envelope.chunks)).toBe(true);
    expect(envelope.chunks.length).toBeGreaterThan(0);
    for (const chunk of envelope.chunks) {
      for (const field of REQUIRED_FIELDS) {
        expect(chunk[field], field).toBeDefined();
      }
      expect(typeof chunk.score).toBe("number");
      expect(chunk.text.trim().length).toBeGreaterThan(0);
    }
    expect(fixtureChunks().every((c) => REQUIRED_FIELDS.every((f) => c[f] !== undefined))).toBe(true);
  });

  it("defaults retrieve top_k to 8", async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      id: `chunk_${i}`,
      source_id: "src",
      text: `Fact number ${i} is recorded in the source material about cells.`,
      locator: `src.md#${i}`,
      score: 1,
      source_filename: "src.md",
    }));
    const vault = new InMemoryVault({ nb: many });
    const hits = await vault.retrieve({ notebook_id: "nb", query: "" });
    expect(hits).toHaveLength(DEFAULT_TOP_K);
  });

  it("HttpVaultRetrieve calls POST /api/v1/notebooks/:id/retrieve and reads { chunks }", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "http://backend.local/api/v1/notebooks/nb_bio/retrieve") {
        expect(init?.method).toBe("POST");
        const body = JSON.parse(String(init?.body));
        expect(body).toEqual({ query: "Mitosis", top_k: 8 });
        return new Response(
          JSON.stringify({
            chunks: [
              {
                id: "chunk_mitosis",
                source_id: "notes-cell-cycle",
                text: "Mitosis produces two identical daughter cells.",
                locator: "notes-cell-cycle.md#mitosis",
                score: 0.9,
                source_filename: "notes-cell-cycle.md",
              },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url === "http://backend.local/api/v1/chunks/chunk_mitosis") {
        return new Response(
          JSON.stringify({
            id: "chunk_mitosis",
            source_id: "notes-cell-cycle",
            text: "Mitosis produces two identical daughter cells.",
            locator: "notes-cell-cycle.md#mitosis",
            score: 0.9,
            source_filename: "notes-cell-cycle.md",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const adapter = new HttpVaultRetrieve("http://backend.local");
    const chunks = await adapter.retrieve({ notebook_id: "nb_bio", query: "Mitosis" });
    expect(chunks).toHaveLength(1);
    expect(chunks[0].id).toBe("chunk_mitosis");
    const one = await adapter.getChunk("chunk_mitosis");
    expect(one?.id).toBe("chunk_mitosis");
    expect(one?.source_filename).toBe("notes-cell-cycle.md");
    expect(one?.locator).toBe("notes-cell-cycle.md#mitosis");
    vi.unstubAllGlobals();
  });

  it("fixture getChunk returns full chunk + source metadata", () => {
    const vault = createFixtureVault();
    const chunk = vault.getChunk("chunk_mitosis");
    expect(chunk).toMatchObject({
      id: "chunk_mitosis",
      source_id: "notes-cell-cycle",
      locator: "notes-cell-cycle.md#mitosis",
      source_filename: "notes-cell-cycle.md",
    });
    expect(chunk?.text).toContain("Mitosis");
  });
});
