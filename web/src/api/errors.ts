import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly body: unknown;

  constructor(status: number, code: string, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.body = body;
  }

  get isTopicsUnconfirmed(): boolean {
    const code = normalizeCode(this.code);
    return this.status === 409 || code === "topicsunconfirmed" || code === "topics_unconfirmed";
  }

  get isInsufficientEvidence(): boolean {
    const code = normalizeCode(this.code);
    return this.status === 422 || code === "insufficientevidence" || code === "insufficient_evidence";
  }
}

function normalizeCode(code: string): string {
  return code.replace(/[\s_-]/g, "").toLowerCase();
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

export async function apiErrorFromResponse(res: Response): Promise<ApiError> {
  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = { message: text };
    }
  }
  const parsed = parseErrorBody(body);
  return new ApiError(
    res.status,
    parsed.code || statusCodeName(res.status),
    parsed.message || res.statusText || `Request failed (${res.status})`,
    body,
  );
}

export function parseErrorBody(body: unknown): { code: string; message: string } {
  if (!body || typeof body !== "object") {
    return { code: "", message: "" };
  }
  const rec = body as ApiErrorBody & Record<string, unknown>;
  let code = String(rec.error || rec.code || "");
  let message = String(rec.message || "");

  if (typeof rec.detail === "string") {
    message = message || rec.detail;
  } else if (rec.detail && typeof rec.detail === "object") {
    const detail = rec.detail as Record<string, unknown>;
    code = String(detail.error || detail.code || code);
    message = String(detail.message || message);
  }

  return { code, message };
}

function statusCodeName(status: number): string {
  if (status === 409) return "topics_unconfirmed";
  if (status === 422) return "insufficient_evidence";
  if (status === 404) return "NotFound";
  if (status === 400) return "BadRequest";
  return `HTTP_${status}`;
}
