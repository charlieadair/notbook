import { randomUUID } from "node:crypto";
import type { Chunk, Quiz, QuizItem, Topic } from "./types.js";
import { isCitableChunk } from "./vault.js";

const GENERIC_DISTRACTORS = [
  "This statement is not present in the retrieved source material.",
  "The retrieved source material does not support this claim.",
  "No citation in the vault states this.",
];

export type SentenceHit = {
  text: string;
  chunk_id: string;
};

export function extractSentences(chunk: Chunk): SentenceHit[] {
  if (!isCitableChunk(chunk)) return [];
  const withoutHeadings = chunk.text.replace(/^#{1,3}\s+.*$/gm, " ");
  const parts = withoutHeadings
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter((s) => s.length >= 24);

  return parts.map((text) => ({ text, chunk_id: chunk.id }));
}

export function keepGroundedItems(items: QuizItem[], knownChunkIds: Set<string>): QuizItem[] {
  return items.filter((item) => isGroundedItem(item, knownChunkIds));
}

export function isGroundedItem(item: QuizItem, knownChunkIds: Set<string>): boolean {
  if (!item.citation_chunk_ids.length) return false;
  return item.citation_chunk_ids.every((id) => Boolean(id) && knownChunkIds.has(id));
}

export function buildGroundedItems(args: {
  quizId: string;
  topics: Topic[];
  evidence: Map<string, Chunk[]>;
}): QuizItem[] {
  const items: QuizItem[] = [];
  const allSentences: SentenceHit[] = [];
  const knownIds = new Set<string>();

  for (const chunks of args.evidence.values()) {
    for (const chunk of chunks) {
      knownIds.add(chunk.id);
      allSentences.push(...extractSentences(chunk));
    }
  }

  for (const topic of args.topics) {
    const chunks = args.evidence.get(topic.id) ?? [];
    const local = chunks.flatMap(extractSentences);
    const used = new Set<string>();

    for (const hit of local) {
      if (used.has(hit.text) || items.length >= 12) continue;
      used.add(hit.text);
      const item = makeItem({
        quizId: args.quizId,
        topic,
        hit,
        allSentences,
      });
      if (item) items.push(item);
      if (used.size >= 2) break;
    }
  }

  return keepGroundedItems(items, knownIds);
}

function makeItem(args: {
  quizId: string;
  topic: Topic;
  hit: SentenceHit;
  allSentences: SentenceHit[];
}): QuizItem | null {
  const distractorTexts = pickDistractors(args.hit, args.allSentences);
  const correctId = randomUUID();
  const choices = shuffleStable([
    { id: correctId, text: args.hit.text },
    ...distractorTexts.map((text) => ({ id: randomUUID(), text })),
  ]);

  if (choices.length < 2) return null;

  return {
    id: randomUUID(),
    quiz_id: args.quizId,
    topic_ids: [args.topic.id],
    stem: `Which of the following is stated in the cited source material about "${args.topic.name}"?`,
    choices,
    correct_choice_id: correctId,
    citation_chunk_ids: [args.hit.chunk_id],
    rationale: args.hit.text,
  };
}

function pickDistractors(correct: SentenceHit, pool: SentenceHit[]): string[] {
  const others = pool
    .filter((s) => s.text !== correct.text && s.chunk_id !== correct.chunk_id)
    .map((s) => s.text);
  const unique = [...new Set(others)];
  const picked = unique.slice(0, 3);
  let i = 0;
  while (picked.length < 3) {
    picked.push(GENERIC_DISTRACTORS[i % GENERIC_DISTRACTORS.length]);
    i += 1;
  }
  return picked;
}

function shuffleStable<T extends { text: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.text.localeCompare(b.text));
}

export function createQuizRecord(notebookId: string, items: QuizItem[]): Quiz {
  const createdAt = new Date().toISOString();
  return {
    id: items[0]?.quiz_id ?? randomUUID(),
    notebook_id: notebookId,
    kind: "pretest",
    item_ids: items.map((item) => item.id),
    created_at: createdAt,
  };
}
