import { API_BASE_URL, joinUrl } from "../lib/config";
import { apiErrorFromResponse } from "./errors";
import {
  toChunks,
  toGeneratedQuiz,
  toGradeAttemptResult,
  toHealth,
  toNotebook,
  toNotebooks,
  toScoreboard,
  toSource,
  toSources,
  toTopics,
  toChunk,
} from "./normalize";
import type {
  Chunk,
  ConfirmTopicsInput,
  GeneratedQuiz,
  GradeAttemptInput,
  GradeAttemptResult,
  Health,
  Notebook,
  Scoreboard,
  Source,
  StudyApi,
  Topic,
} from "./types";

/** Vault paths match `backend/docs/openapi.json` on main (single POST /sources, inspect, HealthOut). */
export type HttpClientOptions = {
  baseUrl?: string;
  fetchFn?: typeof fetch;
};

export class HttpStudyApi implements StudyApi {
  private readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? API_BASE_URL).replace(/\/$/, "");
    this.fetchFn = options.fetchFn ?? fetch.bind(globalThis);
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
    });
    return toSource(data);
  }

  async pasteSource(notebookId: string, input: { filename?: string; text: string }): Promise<Source> {
    const data = await this.request<unknown>(`/notebooks/${notebookId}/sources`, {
      method: "POST",
      json: { filename: input.filename, text: input.text },
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

  private async request<T>(
    path: string,
    init: RequestInit & { json?: unknown } = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    let body = init.body;
    if (init.json !== undefined) {
      headers.set("content-type", "application/json");
      body = JSON.stringify(init.json);
    }
    const res = await this.fetchFn(joinUrl(this.baseUrl, path), {
      ...init,
      headers,
      body,
    });
    if (!res.ok) {
      throw await apiErrorFromResponse(res);
    }
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  }
}
