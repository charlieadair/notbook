import { describe, expect, it, vi } from "vitest";
import { DEFAULT_TOP_K } from "../src/types.js";
import { fixtureChunks, HttpVaultRetrieve, InMemoryVault } from "../src/vault.js";

describe("VaultRetrieve contract", () => {
  it("fixture chunks use Backend field names", () => {
    for (const chunk of fixtureChunks()) {
      expect(chunk.id).toBeTruthy();
      expect(chunk.source_id).toBeTruthy();
      expect(chunk.text.trim().length).toBeGreaterThan(0);
      expect(chunk.locator).toBeTruthy();
      expect(typeof chunk.score).toBe("number");
      expect(chunk.source_filename).toBeTruthy();
    }
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
      expect(String(input)).toBe("http://backend.local/api/v1/notebooks/nb_bio/retrieve");
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
    });
    vi.stubGlobal("fetch", fetchMock);

    const adapter = new HttpVaultRetrieve("http://backend.local");
    const chunks = await adapter.retrieve({ notebook_id: "nb_bio", query: "Mitosis" });
    expect(chunks).toHaveLength(1);
    expect(chunks[0].id).toBe("chunk_mitosis");
    vi.unstubAllGlobals();
  });
});
