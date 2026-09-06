import { isAbortError, isApiError } from "../api/errors";
import type { Source } from "../api/types";
import { extractStatusLabel, normalizeExtractStatus } from "./extractStatus";
import { errorMessage } from "./format";

/** One honest line when the request never finishes or extract did not land. */
export const UPLOAD_HANG_MESSAGE =
  "Upload timed out or extract failed — try paste text or a smaller PDF.";

export function uploadFailureMessage(err: unknown): string {
  if (isAbortError(err) || (isApiError(err) && err.isUploadTimeout)) {
    return UPLOAD_HANG_MESSAGE;
  }
  if (err instanceof TypeError) {
    return UPLOAD_HANG_MESSAGE;
  }
  if (isApiError(err)) {
    const fromExtract = messageFromExtractBody(err.body);
    if (fromExtract) return fromExtract;
    if (err.message.trim()) return err.message;
  }
  return errorMessage(err);
}

/** Prefer Backend extract_status / extract_error when a completed body has them. */
export function sourceUploadFeedback(source: Source): { error: string | null; note: string | null } {
  if (source.extract_status === "failed") {
    return {
      error: source.extract_error?.trim() || `Extract failed for ${source.filename}. Try paste text or a smaller PDF.`,
      note: null,
    };
  }
  return { error: null, note: `Added ${source.filename}.` };
}

function messageFromExtractBody(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const rec = body as Record<string, unknown>;
  if (typeof rec.extract_error === "string" && rec.extract_error.trim()) {
    return rec.extract_error.trim();
  }
  if (rec.extract_status == null) return null;
  const raw = String(rec.extract_status);
  const status = normalizeExtractStatus(raw);
  if (typeof rec.error === "string" && rec.error.includes(" ")) {
    return rec.error.trim();
  }
  if (status === "failed" || status === "pending") {
    return `${extractStatusLabel(status)}. Try paste text or a smaller PDF.`;
  }
  return null;
}
