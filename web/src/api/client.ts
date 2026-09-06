import { API_BASE_URL, UPLOAD_TIMEOUT_MS, joinUrl } from "../lib/config";
import { emptySpawnOffer } from "../lib/spawn";
import { UPLOAD_HANG_MESSAGE } from "../lib/upload";
import { ApiError, apiErrorFromResponse, isAbortError, isApiError } from "./errors";
import {
  toChat,
  toChatMessage,
  toChatMessages,
  toChats,
  toChunk,
  toChunks,
  toGeneratedQuiz,
  toGradeAttemptResult,
  toHandoff,
  toHandoffs,
  toHealth,
  toNotebook,
  toNotebooks,
  toScoreboard,
  toSource,
  toSources,
  toSpawnOffer,
  toTopics,
  asRecord,
  unwrapList,
} from "./normalize";
import type {
  Chat,
  ChatMessage,
  Chunk,
  ConfirmTopicsInput,
  CreateSpecialistsResult,
  GeneratedQuiz,
  GradeAttemptInput,
  GradeAttemptResult,
  Handoff,
  Health,
  Notebook,
  Scoreboard,
  SendChatMessageInput,
  SendChatMessageResult,
  Source,
  SpawnOffer,
  StudyApi,
  Topic,
} from "./types";

/** Vault paths match `backend/docs/openapi.json` on main (single POST /sources, inspect, HealthOut). */
export type HttpClientOptions = {
  baseUrl?: string;
  fetchFn?: typeof fetch;
  /** Override client abort for POST /sources. Default: UPLOAD_TIMEOUT_MS (75s). */
  uploadTimeoutMs?: number;
};

export class HttpStudyApi implements StudyApi {
  private readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;
  private readonly uploadTimeoutMs: number;

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? API_BASE_URL).replace(/\/$/, "");
    this.fetchFn = options.fetchFn ?? fetch.bind(globalThis);
    this.uploadTimeoutMs = options.uploadTimeoutMs ?? UPLOAD_TIMEOUT_MS;
  }

  async health(): Promise<Health> {
    const data = await this.request<unknown>("/health");
    return toHealth(data);
  }

  async listNotebooks(): Promise<Notebook[]> {
    return toNotebooks(await this.request<unknown>("/notebooks"));
  }

  async createNotebook(title: string): Promise<Notebook> {
    const data = await this.request<unknown>("/notebooks", {
      method: "POST",
      json: { title },
    });
    return toNotebook(data);
  }

  async getNotebook(id: string): Promise<Notebook> {
    return toNotebook(await this.request<unknown>(`/notebooks/${id}`));
  }

  async uploadSource(notebookId: string, file: File): Promise<Source> {
    const body = new FormData();
    body.append("file", file);
    const data = await this.request<unknown>(`/notebooks/${notebookId}/sources`, {
      method: "POST",
      body,
      timeoutMs: this.uploadTimeoutMs,
    });
    return toSource(data);
  }

  async pasteSource(notebookId: string, input: { filename?: string; text: string }): Promise<Source> {
    const data = await this.request<unknown>(`/notebooks/${notebookId}/sources`, {
      method: "POST",
      json: { filename: input.filename, text: input.text },
      timeoutMs: this.uploadTimeoutMs,
    });
    return toSource(data);
  }

  async listSources(notebookId: string): Promise<Source[]> {
    return toSources(await this.request<unknown>(`/notebooks/${notebookId}/sources`));
  }

  async listChunks(_notebookId: string, sourceId: string): Promise<Chunk[]> {
    return toChunks(await this.request<unknown>(`/sources/${sourceId}/chunks`));
  }

  async getChunk(chunkId: string): Promise<Chunk> {
    return toChunk(await this.request<unknown>(`/chunks/${chunkId}`));
  }

  async retrieve(notebookId: string, query: string, topK?: number): Promise<Chunk[]> {
    return toChunks(
      await this.request<unknown>(`/notebooks/${notebookId}/retrieve`, {
        method: "POST",
        json: { query, top_k: topK },
      }),
    );
  }

  async proposeTopics(notebookId: string): Promise<Topic[]> {
    return toTopics(
      await this.request<unknown>(`/notebooks/${notebookId}/topics/propose`, { method: "POST" }),
    );
  }

  async confirmTopics(notebookId: string, input: ConfirmTopicsInput = {}): Promise<Topic[]> {
    return toTopics(
      await this.request<unknown>(`/notebooks/${notebookId}/topics/confirm`, {
        method: "POST",
        json: input,
      }),
    );
  }

  async listTopics(notebookId: string): Promise<Topic[]> {
    return toTopics(await this.request<unknown>(`/notebooks/${notebookId}/topics`));
  }

  async createPretest(notebookId: string): Promise<GeneratedQuiz> {
    return toGeneratedQuiz(
      await this.request<unknown>(`/notebooks/${notebookId}/quizzes`, { method: "POST" }),
    );
  }

  async submitAttempt(quizId: string, input: GradeAttemptInput): Promise<GradeAttemptResult> {
    return toGradeAttemptResult(
      await this.request<unknown>(`/quizzes/${quizId}/attempts`, {
        method: "POST",
        json: input,
      }),
    );
  }

  async getScoreboard(notebookId: string): Promise<Scoreboard> {
    return toScoreboard(await this.request<unknown>(`/notebooks/${notebookId}/scoreboard`));
  }

  async getSpawnOffer(notebookId: string): Promise<SpawnOffer> {
    const data = await this.requestOptional<unknown>(`/notebooks/${notebookId}/spawn-offer`);
    return data === undefined ? emptySpawnOffer(notebookId) : toSpawnOffer(data, notebookId);
  }

  async listChats(notebookId: string): Promise<Chat[]> {
    const data = await this.requestOptional<unknown>(`/notebooks/${notebookId}/chats`);
    return data === undefined ? [] : toChats(data);
  }

  async getOrCreateOrchestrator(notebookId: string): Promise<Chat | null> {
    // PR #24: GET and POST are both idempotent get-or-create. GET matches list/chats.
    const data = await this.requestOptional<unknown>(`/notebooks/${notebookId}/chats/orchestrator`);
    if (data === undefined) return null;
    const chats = toChats(data);
    if (chats.length) return chats.find((c) => c.kind === "orchestrator") ?? chats[0];
    const chat = toChat(data);
    return chat.id ? chat : null;
  }

  async getChat(chatId: string, notebookId?: string): Promise<Chat | null> {
    const data = await this.requestOptional<unknown>(`/chats/${chatId}`);
    if (data !== undefined) {
      const chat = toChat(data);
      if (chat.id) return chat;
    }
    if (!notebookId) return null;
    const listed = await this.listChats(notebookId);
    return listed.find((c) => c.id === chatId) ?? null;
  }

  async createSpecialists(notebookId: string, topicIds: string[]): Promise<CreateSpecialistsResult> {
    const data = await this.request<unknown>(`/notebooks/${notebookId}/chats/specialists`, {
      method: "POST",
      json: { topic_ids: topicIds },
    });
    const rec = asRecord(data);
    const warnings = unwrapList<unknown>(rec.warnings, ["warnings"]).map(String);
    const chats = toChats(data);
    if (chats.length) return { chats, warnings };
    const chat = toChat(data);
    return { chats: chat.id ? [chat] : [], warnings };
  }

  async listChatMessages(chatId: string): Promise<ChatMessage[]> {
    const data = await this.requestOptional<unknown>(`/chats/${chatId}/messages`);
    return data === undefined ? [] : toChatMessages(data);
  }

  async sendChatMessage(chatId: string, input: SendChatMessageInput): Promise<SendChatMessageResult> {
    const text = (input.text ?? "").trim();
    const json: Record<string, unknown> = input.generate_quiz
      ? { generate_quiz: true, ...(text ? { text, role: input.role ?? "user" } : {}) }
      : { text, role: input.role ?? "user" };
    const data = await this.requestOptional<unknown>(`/chats/${chatId}/messages`, {
      method: "POST",
      json,
    });
    if (data === undefined) return { message: null };
    const rec = asRecord(data);
    const message = toChatMessage(data);
    return {
      message: message.id || message.text ? message : null,
      quiz: rec.quiz ? toGeneratedQuiz(rec.quiz) : undefined,
    };
  }

  async closeChat(chatId: string): Promise<Handoff> {
    const data = await this.request<unknown>(`/chats/${chatId}/close`, { method: "POST" });
    return toHandoff(data);
  }

  async listHandoffs(notebookId: string): Promise<Handoff[]> {
    const data = await this.requestOptional<unknown>(`/notebooks/${notebookId}/handoffs`);
    return data === undefined ? [] : toHandoffs(data);
  }

  private async requestOptional<T>(
    path: string,
    init: RequestInit & { json?: unknown } = {},
  ): Promise<T | undefined> {
    try {
      return await this.request<T>(path, init);
    } catch (err) {
      if (isApiError(err) && err.isUnavailable) return undefined;
      throw err;
    }
  }

  private async request<T>(
    path: string,
    init: RequestInit & { json?: unknown; timeoutMs?: number } = {},
  ): Promise<T> {
    const { json, timeoutMs, signal: outerSignal, headers: initHeaders, body: initBody, ...rest } = init;
    const headers = new Headers(initHeaders);
    let body = initBody;
    if (json !== undefined) {
      headers.set("content-type", "application/json");
      body = JSON.stringify(json);
    }

    const controller = timeoutMs != null && timeoutMs > 0 ? new AbortController() : undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (controller && timeoutMs) {
      timer = setTimeout(() => controller.abort(), timeoutMs);
      if (outerSignal) {
        if (outerSignal.aborted) controller.abort();
        else outerSignal.addEventListener("abort", () => controller.abort(), { once: true });
      }
    }

    try {
      const res = await this.fetchFn(joinUrl(this.baseUrl, path), {
        ...rest,
        headers,
        body,
        signal: controller?.signal ?? outerSignal,
      });
      if (!res.ok) {
        throw await apiErrorFromResponse(res);
      }
      if (res.status === 204) return undefined as T;
      const text = await res.text();
      if (!text) return undefined as T;
      return JSON.parse(text) as T;
    } catch (err) {
      if (controller?.signal.aborted && isAbortError(err)) {
        throw new ApiError(408, "UploadTimeout", UPLOAD_HANG_MESSAGE);
      }
      throw err;
    } finally {
      if (timer !== undefined) clearTimeout(timer);
    }
  }
}
