import { DEFAULT_MAX_SPAWN } from "./types";
import { offerFromScoreboard } from "../lib/spawn";
import { ApiError } from "./errors";
import type {
  Attempt,
  Chat,
  ChatMessage,
  Chunk,
  ConfirmTopicsInput,
  GeneratedQuiz,
  GradeAttemptInput,
  GradeAttemptResult,
  Handoff,
  Health,
  Notebook,
  Quiz,
  QuizItem,
  Scoreboard,
  SendChatMessageInput,
  Source,
  SpawnOffer,
  StudyApi,
  Topic,
  TopicScore,
} from "./types";

type MockState = {
  notebooks: Notebook[];
  sources: Source[];
  chunks: Chunk[];
  topics: Topic[];
  quizzes: Quiz[];
  items: QuizItem[];
  attempts: Attempt[];
  chats: Chat[];
  messages: ChatMessage[];
  handoffs: Handoff[];
};

function nowIso(): string {
  return new Date().toISOString();
}

function id(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function sentencesFrom(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter((s) => s.length >= 20);
}

export class MockStudyApi implements StudyApi {
  private readonly state: MockState = {
    notebooks: [],
    sources: [],
    chunks: [],
    topics: [],
    quizzes: [],
    items: [],
    attempts: [],
    chats: [],
    messages: [],
    handoffs: [],
  };

  async health(): Promise<Health> {
    return { ok: true, service: "web-mock" };
  }

  async listNotebooks(): Promise<Notebook[]> {
    return [...this.state.notebooks];
  }

  async createNotebook(title: string): Promise<Notebook> {
    const notebook: Notebook = { id: id("nb"), title: title.trim() || "Untitled", created_at: nowIso() };
    this.state.notebooks.push(notebook);
    return notebook;
  }

  async getNotebook(notebookId: string): Promise<Notebook> {
    const found = this.state.notebooks.find((n) => n.id === notebookId);
    if (!found) throw new ApiError(404, "NotFound", `Notebook not found: ${notebookId}`);
    return found;
  }

  async uploadSource(notebookId: string, file: File): Promise<Source> {
    await this.getNotebook(notebookId);
    const fail = /fail/i.test(file.name);
    const source: Source = {
      id: id("src"),
      notebook_id: notebookId,
      filename: file.name,
      type: file.type || guessType(file.name),
      extract_status: fail ? "failed" : "ok",
      chunk_count: 0,
      extract_error: fail ? "OCR / extract failed on this file." : null,
    };
    this.state.sources.push(source);
    if (!fail) {
      const text = `Uploaded file ${file.name}. This mock vault stores a stand-in excerpt so the UI can show chunks. Prefer the real Study API for grounded quizzes.`;
      this.addChunks(source, text, file.name);
    }
    return { ...source };
  }

  async pasteSource(notebookId: string, input: { filename?: string; text: string }): Promise<Source> {
    await this.getNotebook(notebookId);
    const filename = input.filename?.trim() || "pasted.txt";
    const source: Source = {
      id: id("src"),
      notebook_id: notebookId,
      filename,
      type: "text",
      extract_status: "ok",
      chunk_count: 0,
    };
    this.state.sources.push(source);
    this.addChunks(source, input.text, filename);
    return { ...source };
  }

  async listSources(notebookId: string): Promise<Source[]> {
    return this.state.sources.filter((s) => s.notebook_id === notebookId).map((s) => ({ ...s }));
  }

  async listChunks(_notebookId: string, sourceId: string): Promise<Chunk[]> {
    return this.state.chunks.filter((c) => c.source_id === sourceId).map((c) => ({ ...c }));
  }

  async getChunk(chunkId: string): Promise<Chunk> {
    const found = this.state.chunks.find((c) => c.id === chunkId);
    if (!found) throw new ApiError(404, "NotFound", `Chunk not found: ${chunkId}`);
    return { ...found };
  }

  async retrieve(notebookId: string, query: string, topK = 8): Promise<Chunk[]> {
    const q = query.toLowerCase();
    const chunks = this.state.chunks.filter((c) => {
      const source = this.state.sources.find((s) => s.id === c.source_id);
      return source?.notebook_id === notebookId;
    });
    const ranked = q
      ? chunks.filter((c) => c.text.toLowerCase().includes(q) || !q)
      : chunks;
    return ranked.slice(0, topK).map((c) => ({ ...c }));
  }

  async proposeTopics(notebookId: string): Promise<Topic[]> {
    const chunks = await this.retrieve(notebookId, "", 20);
    const names = inferTopicNames(chunks);
    const topics = names.map((name, i) => ({
      id: id("top"),
      notebook_id: notebookId,
      name,
      confirmed: false,
      sort_order: i,
    }));
    this.state.topics = this.state.topics.filter((t) => t.notebook_id !== notebookId).concat(topics);
    return topics.map((t) => ({ ...t }));
  }

  async confirmTopics(notebookId: string, input: ConfirmTopicsInput = {}): Promise<Topic[]> {
    if (input.names && input.names.length > 0) {
      const topics = input.names
        .map((name) => name.trim())
        .filter(Boolean)
        .map((name, i) => ({
          id: id("top"),
          notebook_id: notebookId,
          name,
          confirmed: true,
          sort_order: i,
        }));
      this.state.topics = this.state.topics.filter((t) => t.notebook_id !== notebookId).concat(topics);
      return topics.map((t) => ({ ...t }));
    }
    const allow = input.topic_ids?.length ? new Set(input.topic_ids) : null;
    this.state.topics = this.state.topics.map((t) =>
      t.notebook_id === notebookId
        ? { ...t, confirmed: allow ? allow.has(t.id) || t.confirmed : true }
        : t,
    );
    return this.listTopics(notebookId);
  }

  async listTopics(notebookId: string): Promise<Topic[]> {
    return this.state.topics
      .filter((t) => t.notebook_id === notebookId)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((t) => ({ ...t }));
  }

  async createPretest(notebookId: string): Promise<GeneratedQuiz> {
    const topics = await this.listTopics(notebookId);
    if (!topics.length || topics.some((t) => !t.confirmed)) {
      throw new ApiError(409, "TopicsUnconfirmed", "Confirm every topic before generating a quiz");
    }
    const chunks = await this.retrieve(notebookId, "", 20);
    if (!chunks.length) {
      throw new ApiError(422, "InsufficientEvidence", "Vault is empty or has no citable chunks");
    }
    const quiz: Quiz = {
      id: id("quiz"),
      notebook_id: notebookId,
      kind: "pretest",
      item_ids: [],
      created_at: nowIso(),
    };
    const items = buildMockItems(quiz.id, topics, chunks);
    if (!items.length) {
      throw new ApiError(
        422,
        "InsufficientEvidence",
        "No grounded quiz items could be built from retrieved chunks",
      );
    }
    quiz.item_ids = items.map((item) => item.id);
    this.state.quizzes.push(quiz);
    this.state.items.push(...items);
    return { quiz: { ...quiz }, items: items.map((item) => ({ ...item, choices: item.choices.map((c) => ({ ...c })) })) };
  }

  async submitAttempt(quizId: string, input: GradeAttemptInput): Promise<GradeAttemptResult> {
    const quiz = this.state.quizzes.find((q) => q.id === quizId);
    if (!quiz) throw new ApiError(404, "NotFound", `Quiz not found: ${quizId}`);
    const item = this.state.items.find((i) => i.id === input.item_id && i.quiz_id === quizId);
    if (!item) throw new ApiError(404, "NotFound", `Quiz item not found: ${input.item_id}`);
    const attempt: Attempt = {
      id: id("att"),
      item_id: item.id,
      quiz_id: quiz.id,
      notebook_id: quiz.notebook_id,
      selected_choice_id: input.selected_choice_id,
      correct: input.selected_choice_id === item.correct_choice_id,
      topic_ids: [...item.topic_ids],
      created_at: nowIso(),
    };
    this.state.attempts.push(attempt);
    return {
      attempt,
      scoreboard: {
        topics: this.scoresFor(quiz.notebook_id),
        window: 20,
        proficiency_bar: 0.8,
      },
    };
  }

  async getScoreboard(notebookId: string): Promise<Scoreboard> {
    return { topics: this.scoresFor(notebookId), window: 20, proficiency_bar: 0.8 };
  }

  async getSpawnOffer(notebookId: string): Promise<SpawnOffer> {
    await this.getNotebook(notebookId);
    return offerFromScoreboard(notebookId, this.scoresFor(notebookId), DEFAULT_MAX_SPAWN);
  }

  async listChats(notebookId: string): Promise<Chat[]> {
    return this.state.chats.filter((c) => c.notebook_id === notebookId).map((c) => ({ ...c }));
  }

  async getOrCreateOrchestrator(notebookId: string): Promise<Chat> {
    await this.getNotebook(notebookId);
    const existing = this.state.chats.find(
      (c) => c.notebook_id === notebookId && c.kind === "orchestrator" && c.status === "open",
    );
    if (existing) return { ...existing };
    const chat: Chat = {
      id: id("chat"),
      notebook_id: notebookId,
      kind: "orchestrator",
      topic_ids: [],
      status: "open",
      created_at: nowIso(),
    };
    this.state.chats.push(chat);
    return { ...chat };
  }

  async getChat(chatId: string, notebookId?: string): Promise<Chat | null> {
    const found = this.state.chats.find((c) => c.id === chatId && (!notebookId || c.notebook_id === notebookId));
    return found ? { ...found } : null;
  }

  async createSpecialists(notebookId: string, topicIds: string[]): Promise<Chat[]> {
    await this.getNotebook(notebookId);
    const unique = [...new Set(topicIds.filter(Boolean))];
    if (!unique.length) {
      throw new ApiError(400, "BadRequest", "Pick at least one topic for a focus chat");
    }
    if (unique.length > DEFAULT_MAX_SPAWN) {
      throw new ApiError(400, "BadRequest", `Suggest at most ${DEFAULT_MAX_SPAWN} specialist chats`);
    }
    const openSpecialists = this.state.chats.filter(
      (c) => c.notebook_id === notebookId && c.kind === "specialist" && c.status === "open",
    );
    if (openSpecialists.length + unique.length > DEFAULT_MAX_SPAWN) {
      throw new ApiError(409, "TooManySpecialists", "At most two open specialist chats at a time");
    }
    await this.getOrCreateOrchestrator(notebookId);
    const created: Chat[] = unique.map((topicId) => {
      const chat: Chat = {
        id: id("chat"),
        notebook_id: notebookId,
        kind: "specialist",
        topic_ids: [topicId],
        status: "open",
        created_at: nowIso(),
      };
      this.state.chats.push(chat);
      const topic = this.state.topics.find((t) => t.id === topicId);
      this.state.messages.push({
        id: id("msg"),
        chat_id: chat.id,
        role: "assistant",
        text: `Focus chat for ${topic?.name ?? topicId}. Shared scoreboard stays live. Close when you want a handoff back to the orchestrator.`,
        created_at: nowIso(),
      });
      return { ...chat };
    });
    return created;
  }

  async listChatMessages(chatId: string): Promise<ChatMessage[]> {
    return this.state.messages
      .filter((m) => m.chat_id === chatId)
      .map((m) => ({ ...m, citation_chunk_ids: m.citation_chunk_ids ? [...m.citation_chunk_ids] : undefined }));
  }

  async sendChatMessage(chatId: string, input: SendChatMessageInput): Promise<ChatMessage> {
    const chat = this.state.chats.find((c) => c.id === chatId);
    if (!chat) throw new ApiError(404, "NotFound", `Chat not found: ${chatId}`);
    if (chat.status === "closed") throw new ApiError(409, "ChatClosed", "This focus chat is already closed");
    const text = input.text.trim();
    if (!text) throw new ApiError(400, "BadRequest", "Message is empty");
    const user: ChatMessage = {
      id: id("msg"),
      chat_id: chatId,
      role: input.role ?? "user",
      text,
      created_at: nowIso(),
    };
    this.state.messages.push(user);
    if (chat.kind === "specialist" && (input.role ?? "user") === "user") {
      const names = chat.topic_ids.map((tid) => this.state.topics.find((t) => t.id === tid)?.name ?? tid);
      this.state.messages.push({
        id: id("msg"),
        chat_id: chatId,
        role: "assistant",
        text: `Noted. This specialist stays scoped to ${names.join(", ") || "the selected topic"}. I will not invent a lecture here — close the chat to send a handoff to the orchestrator.`,
        created_at: nowIso(),
      });
    }
    return { ...user };
  }

  async closeChat(chatId: string): Promise<Handoff> {
    const chat = this.state.chats.find((c) => c.id === chatId);
    if (!chat) throw new ApiError(404, "NotFound", `Chat not found: ${chatId}`);
    if (chat.kind !== "specialist") {
      throw new ApiError(400, "BadRequest", "Close a specialist chat to write a handoff");
    }
    const existing = this.state.handoffs.find((h) => h.from_chat_id === chatId);
    if (existing) return { ...existing, scoreboard_snapshot: existing.scoreboard_snapshot.map((s) => ({ ...s })) };
    const orchestrator = await this.getOrCreateOrchestrator(chat.notebook_id);
    chat.status = "closed";
    chat.closed_at = nowIso();
    const board = this.scoresFor(chat.notebook_id);
    const snapshot = board.filter((row) => chat.topic_ids.includes(row.topic_id));
    const names = chat.topic_ids.map((tid) => this.state.topics.find((t) => t.id === tid)?.name ?? tid);
    const scoreBits = (snapshot.length ? snapshot : board)
      .map((row) => `${row.name ?? row.topic_id} ${Math.round(row.correct_rate * 100)}% (${row.severity})`)
      .join("; ");
    const handoff: Handoff = {
      id: id("hoff"),
      from_chat_id: chat.id,
      to_chat_id: orchestrator.id,
      topic_ids: [...chat.topic_ids],
      summary: `Handoff from focus chat on ${names.join(", ") || "scoped topics"}. Snapshot: ${scoreBits || "no scores yet"}. Shared scoreboard is the source of truth; mild gaps stay on the orchestrator map.`,
      scoreboard_snapshot: snapshot.length ? snapshot : board,
      created_at: nowIso(),
    };
    this.state.handoffs.push(handoff);
    this.state.messages.push({
      id: id("msg"),
      chat_id: orchestrator.id,
      role: "handoff",
      text: handoff.summary,
      created_at: handoff.created_at,
    });
    return { ...handoff, scoreboard_snapshot: handoff.scoreboard_snapshot.map((s) => ({ ...s })) };
  }

  async listHandoffs(notebookId: string): Promise<Handoff[]> {
    const chatIds = new Set(this.state.chats.filter((c) => c.notebook_id === notebookId).map((c) => c.id));
    return this.state.handoffs
      .filter((h) => chatIds.has(h.to_chat_id) || chatIds.has(h.from_chat_id))
      .map((h) => ({ ...h, scoreboard_snapshot: h.scoreboard_snapshot.map((s) => ({ ...s })) }));
  }

  private addChunks(source: Source, text: string, label: string): void {
    const parts = text
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);
    const bodies = parts.length ? parts : [text.trim()].filter(Boolean);
    for (const [i, body] of bodies.entries()) {
      this.state.chunks.push({
        id: id("chk"),
        text: body,
        source_id: source.id,
        source_label: label,
        locator: `excerpt ${i + 1}`,
      });
    }
    source.chunk_count = this.state.chunks.filter((c) => c.source_id === source.id).length;
  }

  private scoresFor(notebookId: string): TopicScore[] {
    const topics = this.state.topics.filter((t) => t.notebook_id === notebookId);
    return topics.map((topic) => {
      const attempts = this.state.attempts
        .filter((a) => a.notebook_id === notebookId && a.topic_ids.includes(topic.id))
        .slice(-20);
      const correctCount = attempts.filter((a) => a.correct).length;
      const attemptCount = attempts.length;
      const rate = attemptCount ? correctCount / attemptCount : 0;
      const misses = attemptCount - correctCount;
      const proficient = rate >= 0.8;
      const severity = rate < 0.5 || misses >= 3 ? "severe" : rate < 0.8 && attemptCount ? "mild" : "ok";
      return {
        topic_id: topic.id,
        notebook_id: notebookId,
        correct_count: correctCount,
        attempt_count: attemptCount,
        correct_rate: rate,
        proficient,
        severity,
        updated_at: nowIso(),
        name: topic.name,
      };
    });
  }
}

function guessType(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".md")) return "text/markdown";
  if (lower.endsWith(".txt")) return "text/plain";
  if (/\.(png|jpg|jpeg|webp)$/.test(lower)) return "image/*";
  return "application/octet-stream";
}

function inferTopicNames(chunks: Chunk[]): string[] {
  const words = chunks
    .flatMap((c) => c.text.split(/\W+/))
    .map((w) => w.trim())
    .filter((w) => w.length > 4);
  const uniq = [...new Set(words.map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase()))];
  const picked = uniq.slice(0, 3);
  return picked.length ? picked : ["Core ideas", "Key terms"];
}

function buildMockItems(quizId: string, topics: Topic[], chunks: Chunk[]): QuizItem[] {
  const items: QuizItem[] = [];
  for (const topic of topics) {
    const chunk =
      chunks.find((c) => c.text.toLowerCase().includes(topic.name.toLowerCase())) ?? chunks[items.length % chunks.length];
    if (!chunk) continue;
    const stemSource = sentencesFrom(chunk.text)[0] ?? chunk.text.slice(0, 140);
    const correct = {
      id: id("ch"),
      text: stemSource.length > 90 ? `${stemSource.slice(0, 87)}…` : stemSource,
    };
    const itemsForTopic: QuizItem = {
      id: id("item"),
      quiz_id: quizId,
      topic_ids: [topic.id],
      stem: `Which statement is grounded in the vault for “${topic.name}”?`,
      choices: [
        correct,
        { id: id("ch"), text: "This claim is not present in the retrieved source material." },
        { id: id("ch"), text: "The vault does not support this wording." },
      ],
      correct_choice_id: correct.id,
      citation_chunk_ids: [chunk.id],
      rationale: `Because ${chunk.source_label ?? "the source"} says this.`,
    };
    items.push(itemsForTopic);
  }
  return items;
}

export function createFreshMock(): MockStudyApi {
  return new MockStudyApi();
}
