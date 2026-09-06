import { normalizeExtractStatus } from "../lib/extractStatus";
import type {
  Attempt,
  Chunk,
  GeneratedQuiz,
  GradeAttemptResult,
  Health,
  Notebook,
  Quiz,
  QuizItem,
  Scoreboard,
  Source,
  Topic,
  TopicScore,
} from "./types";

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function unwrapList<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  const rec = asRecord(data);
  for (const key of keys) {
    if (Array.isArray(rec[key])) return rec[key] as T[];
  }
  return [];
}

export function unwrapObject<T>(data: unknown, keys: string[]): T {
  const rec = asRecord(data);
  for (const key of keys) {
    const inner = rec[key];
    if (inner && typeof inner === "object" && !Array.isArray(inner)) {
      return inner as T;
    }
  }
  return data as T;
}

export function toNotebook(raw: unknown): Notebook {
  const rec = asRecord(raw);
  return {
    id: String(rec.id ?? rec.notebook_id ?? ""),
    title: String(rec.title ?? rec.name ?? "Untitled notebook"),
    created_at: rec.created_at ? String(rec.created_at) : undefined,
  };
}

export function toSource(raw: unknown): Source {
  const rec = asRecord(raw);
  const chunkCount = Number(rec.chunk_count ?? rec.chunks ?? 0);
  return {
    id: String(rec.id ?? rec.source_id ?? ""),
    notebook_id: rec.notebook_id ? String(rec.notebook_id) : undefined,
    filename: String(rec.filename ?? rec.name ?? rec.original_filename ?? "untitled"),
    type: rec.type ? String(rec.type) : undefined,
    extract_status: normalizeExtractStatus(rec.extract_status ?? rec.status),
    chunk_count: Number.isFinite(chunkCount) ? chunkCount : 0,
    extract_error: rec.extract_error ? String(rec.extract_error) : rec.error ? String(rec.error) : null,
  };
}

export function toChunk(raw: unknown): Chunk {
  const rec = asRecord(raw);
  const locator = rec.locator ?? rec.location ?? null;
  const source = asRecord(rec.source);
  const sourceLabel =
    rec.source_label ?? rec.source_filename ?? rec.filename ?? source.filename ?? null;
  return {
    id: String(rec.id ?? rec.chunk_id ?? ""),
    text: String(rec.text ?? rec.content ?? ""),
    source_id: rec.source_id ? String(rec.source_id) : undefined,
    source_label: sourceLabel ? String(sourceLabel) : undefined,
    locator: locator as Chunk["locator"],
  };
}

export function toTopic(raw: unknown): Topic {
  const rec = asRecord(raw);
  return {
    id: String(rec.id ?? rec.topic_id ?? ""),
    notebook_id: String(rec.notebook_id ?? ""),
    name: String(rec.name ?? rec.title ?? ""),
    confirmed: Boolean(rec.confirmed),
    sort_order: Number(rec.sort_order ?? 0),
    parent_id: rec.parent_id == null ? null : String(rec.parent_id),
  };
}

export function toQuizItem(raw: unknown): QuizItem {
  const rec = asRecord(raw);
  const choices = unwrapList<unknown>(rec.choices ?? rec.options, ["choices", "options"]).map((choice, i) => {
    if (typeof choice === "string") return { id: `c${i}`, text: choice };
    const c = asRecord(choice);
    return {
      id: String(c.id ?? `c${i}`),
      text: String(c.text ?? c.label ?? ""),
    };
  });
  const cites = unwrapList<unknown>(rec.citation_chunk_ids, ["citation_chunk_ids", "citations"]).map(String);
  return {
    id: String(rec.id ?? rec.item_id ?? ""),
    quiz_id: String(rec.quiz_id ?? ""),
    topic_ids: unwrapList<unknown>(rec.topic_ids, ["topic_ids"]).map(String),
    stem: String(rec.stem ?? rec.question ?? rec.prompt ?? ""),
    choices,
    correct_choice_id: rec.correct_choice_id ? String(rec.correct_choice_id) : undefined,
    citation_chunk_ids: cites,
    rationale: rec.rationale ? String(rec.rationale) : undefined,
  };
}

export function toQuiz(raw: unknown): Quiz {
  const rec = asRecord(unwrapObject<unknown>(raw, ["quiz"]));
  const items = unwrapList<unknown>(rec.items ?? rec.questions, ["items", "questions"]);
  const itemIds = unwrapList<unknown>(rec.item_ids, ["item_ids"]).map(String);
  return {
    id: String(rec.id ?? rec.quiz_id ?? ""),
    notebook_id: String(rec.notebook_id ?? ""),
    kind: String(rec.kind ?? "pretest"),
    item_ids: itemIds.length ? itemIds : items.map((item) => toQuizItem(item).id).filter(Boolean),
    created_at: String(rec.created_at ?? new Date().toISOString()),
  };
}

export function toGeneratedQuiz(raw: unknown): GeneratedQuiz {
  const rec = asRecord(raw);
  const quiz = toQuiz(rec.quiz ?? raw);
  const items = unwrapList<unknown>(rec.items ?? rec.questions, ["items", "questions"]).map((item) => {
    const normalized = toQuizItem(item);
    return { ...normalized, quiz_id: normalized.quiz_id || quiz.id };
  });
  return { quiz, items };
}

export function toAttempt(raw: unknown): Attempt {
  const rec = asRecord(unwrapObject<unknown>(raw, ["attempt"]));
  return {
    id: String(rec.id ?? rec.attempt_id ?? ""),
    item_id: String(rec.item_id ?? ""),
    quiz_id: String(rec.quiz_id ?? ""),
    notebook_id: String(rec.notebook_id ?? ""),
    selected_choice_id: String(rec.selected_choice_id ?? rec.answer ?? ""),
    correct: Boolean(rec.correct),
    topic_ids: unwrapList<unknown>(rec.topic_ids, ["topic_ids"]).map(String),
    created_at: String(rec.created_at ?? new Date().toISOString()),
  };
}

export function toTopicScore(raw: unknown): TopicScore {
  const rec = asRecord(raw);
  const rate = Number(rec.correct_rate ?? 0);
  return {
    topic_id: String(rec.topic_id ?? rec.id ?? ""),
    notebook_id: String(rec.notebook_id ?? ""),
    correct_count: Number(rec.correct_count ?? 0),
    attempt_count: Number(rec.attempt_count ?? 0),
    correct_rate: Number.isFinite(rate) ? rate : 0,
    proficient: Boolean(rec.proficient),
    severity: rec.severity === "mild" || rec.severity === "severe" ? rec.severity : "ok",
    updated_at: String(rec.updated_at ?? ""),
    name: rec.name ? String(rec.name) : rec.topic_name ? String(rec.topic_name) : undefined,
  };
}

export function toGradeAttemptResult(raw: unknown): GradeAttemptResult {
  const rec = asRecord(raw);
  const scoreboard = asRecord(rec.scoreboard);
  return {
    attempt: toAttempt(rec.attempt ?? raw),
    scores: unwrapList<unknown>(rec.scores ?? rec.topic_scores ?? scoreboard.topics ?? rec.scoreboard, [
      "scores",
      "topic_scores",
      "topics",
    ]).map(toTopicScore),
  };
}

export function toScoreboard(raw: unknown): Scoreboard {
  const rec = asRecord(raw);
  return {
    topics: unwrapList<unknown>(raw, ["topics", "scoreboard", "items"]).map(toTopicScore),
    window: Number(rec.window ?? 20),
    proficiency_bar: Number(rec.proficiency_bar ?? 0.8),
  };
}

export function toHealth(raw: unknown): Health {
  const rec = asRecord(raw);
  const status = String(rec.status ?? "").toLowerCase();
  const ok =
    typeof rec.ok === "boolean"
      ? rec.ok
      : status
        ? status === "ok" || status === "healthy" || status === "up"
        : true;
  return { ok, service: rec.service ? String(rec.service) : undefined };
}

export function toNotebooks(raw: unknown): Notebook[] {
  return unwrapList<unknown>(raw, ["notebooks", "items"]).map(toNotebook);
}

export function toSources(raw: unknown): Source[] {
  return unwrapList<unknown>(raw, ["sources", "items"]).map(toSource);
}

export function toChunks(raw: unknown): Chunk[] {
  return unwrapList<unknown>(raw, ["chunks", "items"]).map(toChunk);
}

export function toTopics(raw: unknown): Topic[] {
  return unwrapList<unknown>(raw, ["topics", "items"]).map(toTopic);
}
