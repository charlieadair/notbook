export type ExtractStatus = "ok" | "failed" | "pending";

export type Notebook = {
  id: string;
  title: string;
  created_at?: string;
};

export type Source = {
  id: string;
  notebook_id?: string;
  filename: string;
  type?: string;
  extract_status: ExtractStatus;
  chunk_count: number;
  extract_error?: string | null;
};

export type ChunkLocator = {
  page?: number | string;
  region?: string;
  label?: string;
};

export type Chunk = {
  id: string;
  text: string;
  source_id?: string;
  source_label?: string;
  locator?: string | ChunkLocator | null;
};

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

/** POST /notebooks/{id}/quizzes */
export type GeneratedQuiz = {
  quiz: Quiz;
  items: QuizItem[];
};

/** POST …/topics/propose and POST …/topics/confirm */
export type TopicsResponse = {
  topics: Topic[];
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
  name?: string;
};

export type Scoreboard = {
  topics: TopicScore[];
  window: number;
  proficiency_bar: number;
};

export type ConfirmTopicsInput = {
  topic_ids?: string[];
  names?: string[];
};

export type GradeAttemptInput = {
  item_id: string;
  selected_choice_id: string;
};

/** POST /quizzes/{id}/attempts */
export type GradeAttemptResult = {
  attempt: Attempt;
  scoreboard: Scoreboard;
};

export type Health = {
  ok: boolean;
  service?: string;
};

export type ApiErrorBody = {
  error?: string;
  code?: string;
  message?: string;
  detail?: unknown;
};

export interface StudyApi {
  health(): Promise<Health>;
  listNotebooks(): Promise<Notebook[]>;
  createNotebook(title: string): Promise<Notebook>;
  getNotebook(id: string): Promise<Notebook>;
  uploadSource(notebookId: string, file: File): Promise<Source>;
  pasteSource(notebookId: string, input: { filename?: string; text: string }): Promise<Source>;
  listSources(notebookId: string): Promise<Source[]>;
  listChunks(notebookId: string, sourceId: string): Promise<Chunk[]>;
  getChunk(chunkId: string): Promise<Chunk>;
  retrieve(notebookId: string, query: string, topK?: number): Promise<Chunk[]>;
  proposeTopics(notebookId: string): Promise<Topic[]>;
  confirmTopics(notebookId: string, input?: ConfirmTopicsInput): Promise<Topic[]>;
  listTopics(notebookId: string): Promise<Topic[]>;
  createPretest(notebookId: string): Promise<GeneratedQuiz>;
  submitAttempt(quizId: string, input: GradeAttemptInput): Promise<GradeAttemptResult>;
  getScoreboard(notebookId: string): Promise<Scoreboard>;
}
