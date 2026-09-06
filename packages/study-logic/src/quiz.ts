import { randomUUID } from "node:crypto";
import type { Chunk, Quiz, QuizItem, Topic } from "./types.js";
import { isCitableChunk } from "./vault.js";

export const MAX_CHOICE_CHARS = 100;
export const MAX_RAW_BLOB_CHARS = 150;
export const SOURCE_RECALL_PHRASE = "stated in the cited source";

const GENERIC_DISTRACTORS = [
  "a lower bound on growth",
  "the exact runtime",
  "average-case performance only",
  "the reverse of this relationship",
  "an unrelated later stage of the same process",
  "a quantity that is not defined for this topic",
];

const KIND_DISTRACTORS: Record<string, string[]> = {
  describes: ["a lower bound on growth", "the exact runtime", "average-case performance only"],
  definition: ["the reverse of this process", "an unrelated later stage", "a quantity that is not defined here"],
  produces: ["four identical diploid cells", "no change in chromosome number", "a single unchanged parent cell"],
  converts: ["chemical energy into light", "heat into mechanical motion", "sugars into incoming light"],
  when: ["during interphase only", "after the process has already finished", "it does not occur in this process"],
  where: ["in the cytoplasm only", "outside the cell", "in an unrelated organelle"],
  stages: ["interphase, cytokinesis, and apoptosis", "a single undivided step", "only the final checkpoint"],
  why: ["it reports a lower bound instead", "it measures exact wall-clock time", "it is never used in practice"],
  property: ["the reverse of this relationship", "an unrelated later stage", "a quantity that is not defined here"],
};

const SOURCE_RECALL_STEM = /stated in the cited source|which of the following is stated|according to the (?:cited )?source/i;
const AGENDA = /\b(agenda|overview|today we will|table of contents|learning objectives)\b/i;
const TRAILING_PREDICATE = /^(includes?|increases?|produces?|occurs?|contains?|creates?)\b/i;

export type SentenceHit = {
  text: string;
  chunk_id: string;
  source_filename?: string;
};

type ConceptDraft = {
  stem: string;
  correct: string;
  kind: string;
};

type Pattern = {
  re: RegExp;
  kind: string;
};

const PATTERNS: Pattern[] = [
  { re: /^(?:The\s+)?stages\s+of\s+(?<subj>.+?)\s+(?:are|include)\s+(?<obj>.+)$/i, kind: "stages" },
  { re: /^During\s+(?<when>.+?),\s+(?<obj>.+)$/i, kind: "when" },
  { re: /^(?<subj>.+?)\s+occurs?\s+during\s+(?<obj>.+)$/i, kind: "when" },
  { re: /^(?<subj>.+?)\s+occurs?\s+in\s+(?<obj>.+)$/i, kind: "where" },
  { re: /^(?<subj>.+?)\s+describes?\s+(?<obj>.+)$/i, kind: "describes" },
  { re: /^(?<subj>.+?)\s+means\s+(?<obj>.+)$/i, kind: "definition" },
  { re: /^(?<subj>.+?)\s+converts?\s+(?<obj>.+)$/i, kind: "converts" },
  { re: /^(?<subj>.+?)\s+produces?\s+(?<obj>.+)$/i, kind: "produces" },
  { re: /(?:we\s+)?(?:colloquially\s+)?use\s+(?<subj>.+?)\s+because\s+(?<obj>.+)/i, kind: "why" },
  { re: /^(?<subj>.+?)\s+includes?\s+(?<obj>.+)$/i, kind: "property" },
  { re: /^(?<subj>.+?)\s+(?:is|are)\s+(?<obj>.+)$/i, kind: "definition" },
];

export function extractSentences(chunk: Chunk): SentenceHit[] {
  if (!isCitableChunk(chunk)) return [];
  const withoutHeadings = chunk.text.replace(/^#{1,3}\s+.*$/gm, " ");
  return withoutHeadings
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter((text) => text.length >= 24 && usableEvidence(text))
    .map((text) => ({ text, chunk_id: chunk.id, source_filename: chunk.source_filename }));
}

export function keepGroundedItems(items: QuizItem[], knownChunkIds: Set<string>): QuizItem[] {
  return items.filter((item) => isGroundedItem(item, knownChunkIds));
}

export function isGroundedItem(item: QuizItem, knownChunkIds: Set<string>): boolean {
  if (!item.citation_chunk_ids.length) return false;
  return item.citation_chunk_ids.every((id) => Boolean(id) && knownChunkIds.has(id));
}

export function isExamShapedItem(item: QuizItem): boolean {
  if (item.stem.toLowerCase().includes(SOURCE_RECALL_PHRASE) || SOURCE_RECALL_STEM.test(item.stem)) {
    return false;
  }
  const correct = item.choices.find((c) => c.id === item.correct_choice_id);
  if (!correct || !isCleanChoice(correct.text)) return false;
  if (!item.choices.every((c) => isCleanChoice(c.text))) return false;
  if (!item.citation_chunk_ids.length) return false;
  if (!item.rationale || !item.rationale.toLowerCase().includes("because [")) return false;
  return true;
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
    let made = 0;

    for (const hit of local) {
      if (used.has(hit.text) || items.length >= 12) continue;
      const item = makeItem({ quizId: args.quizId, topic, hit, allSentences });
      if (!item) continue;
      used.add(hit.text);
      items.push(item);
      made += 1;
      if (made >= 2) break;
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
  const drafted = conceptualize(args.topic, args.hit.text);
  if (!drafted || !isCleanChoice(drafted.correct) || isRawBlob(drafted.correct)) return null;
  if (SOURCE_RECALL_STEM.test(drafted.stem)) return null;

  const distractorTexts = pickDistractors(drafted.correct, args.allSentences, KIND_DISTRACTORS[drafted.kind] ?? []);
  const correctId = randomUUID();
  const choices = shuffleStable([
    { id: correctId, text: drafted.correct },
    ...distractorTexts.map((text) => ({ id: randomUUID(), text })),
  ]);
  if (choices.length < 2) return null;

  const item: QuizItem = {
    id: randomUUID(),
    quiz_id: args.quizId,
    topic_ids: [args.topic.id],
    stem: drafted.stem,
    choices,
    correct_choice_id: correctId,
    citation_chunk_ids: [args.hit.chunk_id],
    rationale: groundedRationale(args.hit),
  };
  return isExamShapedItem(item) ? item : null;
}

function conceptualize(topic: Topic, sentence: string): ConceptDraft | null {
  const text = sentence.replace(/\s+/g, " ").trim().replace(/[.;:]+$/, "");
  if (!text || !usableEvidence(`${text}.`)) return null;

  for (const { re, kind } of PATTERNS) {
    const match = text.match(re);
    if (!match?.groups) continue;
    const draft = draftFromMatch(topic, kind, match.groups);
    if (draft) return draft;
  }
  return fallbackDraft(topic, text);
}

function draftFromMatch(topic: Topic, kind: string, groups: Record<string, string>): ConceptDraft | null {
  const obj = firstClause(groups.obj ?? "");
  if (!obj) return null;
  const correct = shortenPhrase(obj);
  if (!isCleanChoice(correct)) return null;
  const subject = prettySubject(groups.subj ?? topic.name, topic);

  if (kind === "stages") return { stem: `What are the stages of ${subject}?`, correct, kind };
  if (kind === "when" && groups.when) {
    return { stem: `What happens during ${groups.when.trim()}?`, correct, kind };
  }
  if (kind === "when") {
    const when = correct.toLowerCase().startsWith("during ") ? correct : `during ${correct}`;
    return { stem: `When does ${subject} occur?`, correct: when, kind };
  }
  if (kind === "where") {
    const place = correct.toLowerCase().startsWith("in ") ? correct : `in ${correct}`;
    const stem = pluralSubject(subject) ? `Where do ${subject} occur?` : `Where does ${subject} occur?`;
    return { stem, correct: place, kind };
  }
  if (kind === "describes") return { stem: `What does ${subject} describe?`, correct, kind };
  if (kind === "converts") return { stem: `What does ${subject} convert?`, correct, kind };
  if (kind === "produces") return { stem: `What does ${subject} produce?`, correct, kind };
  if (kind === "why") return { stem: `Why is ${subject} used?`, correct, kind };
  if (kind === "definition") {
    const verb = pluralSubject(subject) ? "are" : "is";
    return { stem: `What ${verb} ${subject}?`, correct, kind };
  }
  return { stem: `What does ${subject} include?`, correct, kind };
}

function fallbackDraft(topic: Topic, sentence: string): ConceptDraft | null {
  const match = sentence.match(/\b(?:is|are|describes?|means?|produces?|converts?|occurs?|includes?|uses?)\s+(.+)$/i);
  if (!match) return null;
  const phrase = shortenPhrase(firstClause(match[1]));
  if (!isCleanChoice(phrase)) return null;
  if (phrase.replace(/\.$/, "") === sentence.replace(/\.$/, "") && phrase.length > MAX_CHOICE_CHARS) {
    return null;
  }
  return {
    stem: `Which of the following best describes ${topic.name}?`,
    correct: phrase,
    kind: "property",
  };
}

function pickDistractors(correct: string, pool: SentenceHit[], preferred: string[]): string[] {
  const target = correct.toLowerCase();
  const picked: string[] = [];
  const dummy: Topic = { id: "", notebook_id: "", name: "", confirmed: true, sort_order: 0 };

  const add = (text: string) => {
    const phrase = shortenPhrase(text);
    if (!isCleanChoice(phrase)) return;
    if (phrase.toLowerCase() === target) return;
    if (picked.some((existing) => existing.toLowerCase() === phrase.toLowerCase())) return;
    picked.push(phrase);
  };

  for (const text of preferred) {
    add(text);
    if (picked.length >= 3) return picked;
  }
  for (const hit of pool) {
    const draft = conceptualize(dummy, hit.text);
    if (draft) add(draft.correct);
    if (picked.length >= 3) return picked;
  }
  for (const text of GENERIC_DISTRACTORS) {
    add(text);
    if (picked.length >= 3) break;
  }
  return picked.slice(0, 3);
}

function groundedRationale(hit: SentenceHit): string {
  const source = hit.source_filename || hit.chunk_id;
  return `because [${source}] says "${shortExcerpt(hit.text)}"`;
}

function shortExcerpt(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 140) return cleaned;
  return `${cleaned.slice(0, 139).replace(/\s+\S*$/, "")}…`;
}

function prettySubject(raw: string, topic: Topic): string {
  let cleaned = raw.replace(/\s+/g, " ").trim().replace(/[.;:]+$/, "");
  cleaned = cleaned.replace(/^(?:the|a|an)\s+/i, "");
  if (!cleaned) return topic.name;
  if (topic.name && cleaned.toLowerCase().includes(topic.name.toLowerCase())) return topic.name;
  if (topic.name && topic.name.toLowerCase().includes(cleaned.toLowerCase())) return topic.name;
  if (cleaned[0] === cleaned[0].toLowerCase()) return cleaned[0].toUpperCase() + cleaned.slice(1);
  return cleaned;
}

function pluralSubject(subject: string): boolean {
  const lowered = subject.toLowerCase();
  if (lowered.endsWith("sis") || lowered.endsWith("ss")) return false;
  return lowered.endsWith("s") || lowered.includes("reactions") || lowered.includes("stages");
}

function firstClause(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim().replace(/[.;:]+$/, "");
  if (!cleaned) return "";
  const parts = cleaned.split(/\s+and\s+/, 2);
  if (parts.length === 2 && TRAILING_PREDICATE.test(parts[1])) return parts[0].replace(/[ ,]+$/, "");
  return cleaned;
}

function shortenPhrase(text: string, limit = MAX_CHOICE_CHARS): string {
  const cleaned = String(text).replace(/\s+/g, " ").trim().replace(/[.;:]+$/, "");
  if (cleaned.length <= limit) return cleaned;
  for (const sep of ["; ", " — ", " - ", ", and ", " that ", ", "]) {
    const head = cleaned.split(sep, 1)[0].trim();
    if (head.length >= 12 && head.length <= limit) return head;
  }
  return cleaned.slice(0, limit).replace(/\s+\S*$/, "").replace(/[ ,;:]+$/, "");
}

function usableEvidence(text: string): boolean {
  const stripped = text.trim();
  if (stripped.endsWith("?") && !/\b(because|is|are|means|describes)\b/i.test(stripped)) return false;
  if (AGENDA.test(stripped)) return false;
  const letters = [...stripped].filter((ch) => /[A-Za-z]/.test(ch)).length;
  if (letters < 16) return false;
  if (letters / Math.max(stripped.length, 1) < 0.4) return false;
  return true;
}

function isCleanChoice(text: string): boolean {
  if (!text || text.includes("\n")) return false;
  const cleaned = text.replace(/\s+/g, " ").trim();
  return cleaned.length >= 2 && cleaned.length <= MAX_CHOICE_CHARS;
}

function isRawBlob(text: string): boolean {
  return text.replace(/\s+/g, " ").trim().length > MAX_RAW_BLOB_CHARS;
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
