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

/** S1 chat tree — Study-logic issue #22. Shapes stay flexible until OpenAPI lands. */
export const DEFAULT_MAX_SPAWN = 2;

export type ChatKind = "orchestrator" | "specialist";
export type ChatStatus = "open" | "closed";
export type ChatMessageRole = "user" | "assistant" | "handoff" | "system";
export type SpawnSeverity = "mild" | "severe";

export type Chat = {
  id: string;
  notebook_id: string;
  kind: ChatKind;
  topic_ids: string[];
  status: ChatStatus;
  created_at: string;
  closed_at?: string | null;
};

export type ChatMessage = {
  id: string;
  chat_id: string;
  role: ChatMessageRole;
  text: string;
  created_at: string;
  citation_chunk_ids?: string[];
};

export type SpawnCandidate = {
  topic_id: string;
  severity: SpawnSeverity;
  reason: string;
};

export type SpawnOffer = {
  notebook_id: string;
  candidates: SpawnCandidate[];
  max_spawn: number;
};

export type Handoff = {
  id: string;
  from_chat_id: string;
  to_chat_id: string;
  topic_ids: string[];
  summary: string;
  scoreboard_snapshot: TopicScore[];
  created_at: string;
};

export type SendChatMessageInput = {
  text: string;
  role?: ChatMessageRole;
  generate_quiz?: boolean;
};

export type CreateSpecialistsResult = {
  chats: Chat[];
  warnings: string[];
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

  /** GET /notebooks/:id/spawn-offer — empty offer on 404/501. */
  getSpawnOffer(notebookId: string): Promise<SpawnOffer>;
  /** GET /notebooks/:id/chats — [] on 404/501. */
  listChats(notebookId: string): Promise<Chat[]>;
  /** GET|POST /notebooks/:id/chats/orchestrator — idempotent get-or-create; null on 404/501. */
  getOrCreateOrchestrator(notebookId: string): Promise<Chat | null>;
  /** GET /chats/:id, else find in notebook chat list; null on 404/501. */
  getChat(chatId: string, notebookId?: string): Promise<Chat | null>;
  /** POST /notebooks/:id/chats/specialists `{ topic_ids }` → `{ chat, warnings }` (one chat). */
  createSpecialists(notebookId: string, topicIds: string[]): Promise<CreateSpecialistsResult>;
  /** GET /chats/:id/messages — [] on 404/501. */
  listChatMessages(chatId: string): Promise<ChatMessage[]>;
  /** POST /chats/:id/messages — null on 404/501. */
  sendChatMessage(chatId: string, input: SendChatMessageInput): Promise<ChatMessage | null>;
  /** POST /chats/:id/close → Handoff into orchestrator. */
  closeChat(chatId: string): Promise<Handoff>;
  /** GET /notebooks/:id/handoffs — [] on 404/501. */
  listHandoffs(notebookId: string): Promise<Handoff[]>;
}
