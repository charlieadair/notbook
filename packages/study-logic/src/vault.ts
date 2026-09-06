import type { Chunk, RetrieveArgs, VaultRetrieve } from "./types.js";

export function isCitableChunk(chunk: Chunk): boolean {
  return Boolean(chunk.id?.trim()) && Boolean(chunk.text?.trim());
}

/**
 * In-memory fixture vault for tests and local smoke.
 * Backend should implement VaultRetrieve against:
 *   POST /notebooks/:id/retrieve  { query, top_k? } → Chunk[]
 *   GET  /chunks/:id              → Chunk
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
    const topK = args.top_k ?? 8;
    const all = this.chunks.get(args.notebook_id) ?? [];
    const query = args.query.trim().toLowerCase();
    if (!query) {
      return all.filter(isCitableChunk).slice(0, topK).map((c) => ({ ...c }));
    }

    const terms = query.split(/\s+/).filter(Boolean);
    const ranked = all
      .filter(isCitableChunk)
      .map((chunk) => ({ chunk, score: scoreChunk(chunk, query, terms) }))
      .filter((row) => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, topK)
      .map((row) => ({ ...row.chunk }));

    return ranked;
  }
}

function scoreChunk(chunk: Chunk, query: string, terms: string[]): number {
  const hay = `${chunk.text} ${chunk.source_label ?? ""} ${chunk.source_id ?? ""}`.toLowerCase();
  let score = 0;
  if (hay.includes(query)) score += 5;
  for (const term of terms) {
    if (hay.includes(term)) score += 1;
  }
  return score;
}

/**
 * HTTP adapter for a real Backend vault. Study-logic consumes these routes;
 * it does not own embeddings or OCR.
 */
export class HttpVaultRetrieve implements VaultRetrieve {
  constructor(private readonly baseUrl: string) {}

  async retrieve(args: RetrieveArgs): Promise<Chunk[]> {
    const url = `${trimSlash(this.baseUrl)}/notebooks/${encodeURIComponent(args.notebook_id)}/retrieve`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query: args.query, top_k: args.top_k }),
    });
    if (!res.ok) {
      throw new Error(`Vault retrieve failed: ${res.status}`);
    }
    const body = (await res.json()) as { chunks?: Chunk[] } | Chunk[];
    return Array.isArray(body) ? body : (body.chunks ?? []);
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

function trimSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export const FIXTURE_NOTEBOOK_ID = "nb_bio";

export function fixtureChunks(): Chunk[] {
  return [
    {
      id: "chunk_mitosis",
      source_id: "notes-cell-cycle",
      source_label: "Mitosis",
      text:
        "# Mitosis\n" +
        "Mitosis is a type of cell division that produces two genetically identical daughter cells. " +
        "The stages of mitosis are prophase, metaphase, anaphase, and telophase. " +
        "During metaphase, chromosomes align at the cell equator.",
    },
    {
      id: "chunk_meiosis",
      source_id: "notes-cell-cycle",
      source_label: "Meiosis",
      text:
        "# Meiosis\n" +
        "Meiosis produces four haploid gametes and includes two rounds of division. " +
        "Crossing over occurs during prophase I and increases genetic variation.",
    },
    {
      id: "chunk_photosynthesis",
      source_id: "notes-energy",
      source_label: "Photosynthesis",
      text:
        "# Photosynthesis\n" +
        "Photosynthesis converts light energy into chemical energy stored in sugars. " +
        "The light-dependent reactions occur in the thylakoid membrane and produce ATP and NADPH.",
    },
  ];
}

export function createFixtureVault(): InMemoryVault {
  return new InMemoryVault({ [FIXTURE_NOTEBOOK_ID]: fixtureChunks() });
}
