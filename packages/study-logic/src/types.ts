export type Topic = {
  id: string;
  notebook_id: string;
  name: string;
  confirmed: boolean;
  sort_order: number;
  parent_id?: string | null;
};

export type QuizChoice = {
  id: string;
  text: string;
};

export type QuizItem = {
  id: string;
  quiz_id: string;
  topic_ids: string[];
  stem: string;
  choices: QuizChoice[];
  correct_choice_id: string;
  citation_chunk_ids: string[];
  rationale?: string;
};

export type Quiz = {
  id: string;
  notebook_id: string;
  kind: "pretest";
  item_ids: string[];
  created_at: string;
};

export type Attempt = {
  id: string;
  item_id: string;
  quiz_id: string;
  notebook_id: string;
  selected_choice_id: string;
  correct: boolean;
  topic_ids: string[];
  created_at: string;
};

export type Severity = "ok" | "mild" | "severe";

export type TopicScore = {
  topic_id: string;
  notebook_id: string;
  correct_count: number;
  attempt_count: number;
  correct_rate: number;
  proficient: boolean;
  severity: Severity;
  updated_at: string;
};

export type Scoreboard = {
  topics: TopicScore[];
  window: number;
  proficiency_bar: number;
};

export const SCORE_WINDOW = 20;
export const PROFICIENCY_BAR = 0.8;
export const SEVERE_RATE = 0.5;
export const SEVERE_MISS_COUNT = 3;

/** Backend retrieve hit. `id` is the citation_chunk_id. */
export type Chunk = {
  id: string;
  source_id: string;
  text: string;
  locator: string;
  score: number;
  source_filename?: string;
};

export type RetrieveResponse = {
  chunks: Chunk[];
};

export const DEFAULT_TOP_K = 8;

export type RetrieveArgs = {
  notebook_id: string;
  query: string;
  top_k?: number;
};

/** Backend vault contract consumed by study-logic. Do not reimplement retrieval here. */
export interface VaultRetrieve {
  retrieve(args: RetrieveArgs): Promise<Chunk[]>;
}

export type ConfirmTopicsInput = {
  /** Explicit topic list (SPEC §4/§12). Already confirmed; skips propose. */
  names?: string[];
  /** Alias for `names`. */
  topics?: string[];
  topic_ids?: string[];
};

export type GradeAttemptInput = {
  item_id: string;
  selected_choice_id: string;
};

export type GradeAttemptResult = {
  attempt: Attempt;
  scores: TopicScore[];
};

export type GeneratedQuiz = {
  quiz: Quiz;
  items: QuizItem[];
};
