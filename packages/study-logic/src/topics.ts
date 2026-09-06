import { randomUUID } from "node:crypto";
import type { Chunk, Topic } from "./types.js";

const DEFINITION = /^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+is\s+/;
const HEADING = /^#{1,3}\s+(.+)$/;

/** Infer unconfirmed topic names from vault chunk text. Never invents course facts. */
export function proposeTopicNames(chunks: Chunk[]): string[] {
  const names: string[] = [];
  const seen = new Set<string>();

  const add = (raw: string) => {
    const name = raw.replace(/\s+/g, " ").trim();
    const key = name.toLowerCase();
    if (!name || key.length < 2 || seen.has(key)) return;
    seen.add(key);
    names.push(name);
  };

  for (const chunk of chunks) {
    if (chunk.source_label) add(chunk.source_label);
    for (const line of chunk.text.split(/\r?\n/)) {
      const heading = line.trim().match(HEADING);
      if (heading) add(heading[1]);
      const def = line.trim().match(DEFINITION);
      if (def) add(def[1]);
    }
  }

  return names;
}

export function topicsFromNames(
  notebookId: string,
  names: string[],
  confirmed: boolean,
): Topic[] {
  return names.map((name, index) => ({
    id: randomUUID(),
    notebook_id: notebookId,
    name,
    confirmed,
    sort_order: index,
    parent_id: null,
  }));
}

export function allTopicsConfirmed(topics: Topic[]): boolean {
  return topics.length > 0 && topics.every((t) => t.confirmed);
}
