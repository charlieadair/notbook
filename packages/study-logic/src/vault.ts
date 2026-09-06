import { DEFAULT_TOP_K, type Chunk, type RetrieveArgs, type VaultRetrieve } from "./types.js";

export function isCitableChunk(chunk: Chunk): boolean {
  return Boolean(chunk.id?.trim()) && Boolean(chunk.text?.trim());
}

/**
 * In-memory fixture vault for tests and local smoke.
 * Backend owns the real vault (S0 sketch):
 *   POST /notebooks/:id/retrieve  { query } → citable chunks
 *   GET  /chunks/:id
 */
export class InMemoryVault implements VaultRetrieve {
  private readonly chunks = new Map<string, Chunk[]>();

  constructor(seed?: Record<string, Chunk[]>) {
    if (seed) {
      for (const [notebookId, list] of Object.entries(seed)) {
        this.chunks.set(notebookId, list.map((c) => ({ ...c })));
      }
    }
  }

  seed(notebookId: string, chunks: Chunk[]): void {
    this.chunks.set(notebookId, chunks.map((c) => ({ ...c })));
  }

  getChunk(id: string): Chunk | undefined {
    for (const list of this.chunks.values()) {
      const found = list.find((c) => c.id === id);
      if (found) return { ...found };
    }
    return undefined;
  }

  allChunks(notebookId: string): Chunk[] {
    return (this.chunks.get(notebookId) ?? []).map((c) => ({ ...c }));
  }

  async retrieve(args: RetrieveArgs): Promise<Chunk[]> {
    const topK = args.top_k ?? DEFAULT_TOP_K;
    const all = this.chunks.get(args.notebook_id) ?? [];
    const query = args.query.trim().toLowerCase();
    if (!query) {
      return all
        .filter(isCitableChunk)
        .slice(0, topK)
        .map((c) => ({ ...c, score: c.score ?? 1 }));
    }

    const terms = query.split(/\s+/).filter(Boolean);
    return all
      .filter(isCitableChunk)
      .map((chunk) => ({ chunk, score: scoreChunk(chunk, query, terms) }))
      .filter((row) => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, topK)
      .map((row) => ({ ...row.chunk, score: row.score }));
  }
}

function scoreChunk(chunk: Chunk, query: string, terms: string[]): number {
  const hay = `${chunk.text} ${chunk.source_filename ?? ""} ${chunk.source_id} ${chunk.locator}`.toLowerCase();
  let score = 0;
  if (hay.includes(query)) score += 5;
  for (const term of terms) {
    if (hay.includes(term)) score += 1;
  }
  return score;
}

/**
 * HTTP adapter for Backend vault. Calls the S0 sketch paths:
 *   POST /notebooks/:id/retrieve  { query }
 *   GET  /chunks/:id
 */
export class HttpVaultRetrieve implements VaultRetrieve {
  constructor(private readonly baseUrl: string) {}

  async retrieve(args: RetrieveArgs): Promise<Chunk[]> {
    const url = `${trimSlash(this.baseUrl)}/notebooks/${encodeURIComponent(args.notebook_id)}/retrieve`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: args.query, top_k: args.top_k ?? DEFAULT_TOP_K }),
    });
    if (!res.ok) {
      throw new Error(`Vault retrieve failed: ${res.status}`);
    }
    return parseRetrieveBody(await res.json());
  }

  async getChunk(id: string): Promise<Chunk | undefined> {
    const url = `${trimSlash(this.baseUrl)}/chunks/${encodeURIComponent(id)}`;
    const res = await fetch(url);
    if (res.status === 404) return undefined;
    if (!res.ok) {
      throw new Error(`Vault getChunk failed: ${res.status}`);
    }
    return (await res.json()) as Chunk;
  }
}

function parseRetrieveBody(body: unknown): Chunk[] {
  if (Array.isArray(body)) return body as Chunk[];
  if (body && typeof body === "object" && Array.isArray((body as { chunks?: unknown }).chunks)) {
    return (body as { chunks: Chunk[] }).chunks;
  }
  return [];
}

function trimSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export const FIXTURE_NOTEBOOK_ID = "nb_bio";

export function fixtureChunks(): Chunk[] {
  return [
    {
      id: "chunk_mitosis",
      source_id: "notes-cell-cycle",
      text:
        "# Mitosis\n" +
        "Mitosis is a type of cell division that produces two genetically identical daughter cells. " +
        "The stages of mitosis are prophase, metaphase, anaphase, and telophase. " +
        "During metaphase, chromosomes align at the cell equator.",
      locator: "notes-cell-cycle.md#mitosis",
      score: 1,
      source_filename: "notes-cell-cycle.md",
    },
    {
      id: "chunk_meiosis",
      source_id: "notes-cell-cycle",
      text:
        "# Meiosis\n" +
        "Meiosis produces four haploid gametes and includes two rounds of division. " +
        "Crossing over occurs during prophase I and increases genetic variation.",
      locator: "notes-cell-cycle.md#meiosis",
      score: 1,
      source_filename: "notes-cell-cycle.md",
    },
    {
      id: "chunk_photosynthesis",
      source_id: "notes-energy",
      text:
        "# Photosynthesis\n" +
        "Photosynthesis converts light energy into chemical energy stored in sugars. " +
        "The light-dependent reactions occur in the thylakoid membrane and produce ATP and NADPH.",
      locator: "notes-energy.md#photosynthesis",
      score: 1,
      source_filename: "notes-energy.md",
    },
  ];
}

export function createFixtureVault(): InMemoryVault {
  return new InMemoryVault({ [FIXTURE_NOTEBOOK_ID]: fixtureChunks() });
}
