import { randomUUID } from "node:crypto";
import type { Chunk, Topic } from "./types.js";

const DEFINITION = /^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+is\s+/;
const FIRST_CLAUSE = /^([A-Z][A-Za-z0-9][A-Za-z0-9 \-]{1,48})\s+(?:is|are|was|were)\s+/;
const HEADING = /^#{1,3}\s+(.+)$/;
const WORD = /[A-Za-z0-9\-]+/g;

const TOPIC_STOPWORDS = new Set([
  "this",
  "that",
  "these",
  "those",
  "what",
  "which",
  "who",
  "whom",
  "whose",
  "where",
  "when",
  "why",
  "how",
  "there",
  "here",
  "it",
  "they",
  "we",
  "you",
  "i",
  "a",
  "an",
  "the",
]);

function words(name: string): string[] {
  return name.match(WORD) ?? [];
}

function isStopwordName(name: string): boolean {
  const tokens = words(name);
  return tokens.length === 0 || tokens.every((token) => TOPIC_STOPWORDS.has(token.toLowerCase()));
}

function isTermLike(name: string): boolean {
  const tokens = words(name);
  if (!tokens.length || TOPIC_STOPWORDS.has(tokens[0].toLowerCase()) || isStopwordName(name)) {
    return false;
  }
  if (tokens.length >= 2) return true;
  const token = tokens[0];
  if (token === token.toUpperCase() && token.length >= 2) return true;
  return token.length >= 4;
}

function* iterSentences(text: string): Generator<string> {
  for (const line of text.split(/\r?\n/)) {
    const stripped = line.trim();
    if (!stripped || HEADING.test(stripped)) continue;
    for (const part of stripped.split(/(?<=[.!?])\s+/)) {
      const sentence = part.trim();
      if (sentence) yield sentence;
    }
  }
}

/** Infer unconfirmed topic names from vault chunk text. Never invents course facts. */
export function proposeTopicNames(chunks: Chunk[]): string[] {
  const names: string[] = [];
  const seen = new Set<string>();

  const add = (raw: string, termLike = false) => {
    const name = raw.replace(/\s+/g, " ").trim().replace(/^[ .!?]+|[ .!?]+$/g, "");
    const key = name.toLowerCase();
    if (!name || key.length < 2 || seen.has(key)) return;
    if (isStopwordName(name)) return;
    if (termLike && !isTermLike(name)) return;
    seen.add(key);
    names.push(name);
  };

  for (const chunk of chunks) {
    const stem = chunk.source_filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
    if (/^[A-Z]/.test(stem) && stem.split(" ").length <= 4) add(stem);
    for (const line of chunk.text.split(/\r?\n/)) {
      const heading = line.trim().match(HEADING);
      if (heading) add(heading[1]);
    }
    for (const sentence of iterSentences(chunk.text)) {
      const def = sentence.match(DEFINITION);
      if (def) {
        add(def[1], true);
        continue;
      }
      const clause = sentence.match(FIRST_CLAUSE);
      if (clause) add(clause[1], true);
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
