import { ApiError } from "./errors";
import type {
  Attempt,
  Chunk,
  ConfirmTopicsInput,
  GeneratedQuiz,
  GradeAttemptInput,
  GradeAttemptResult,
  Health,
  Notebook,
  Quiz,
  QuizItem,
  Scoreboard,
  Source,
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
