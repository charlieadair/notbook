import type { ExtractStatus } from "../api/types";

const OK = new Set(["ok", "success", "ready", "complete", "completed", "done"]);
const FAILED = new Set(["failed", "error", "fail", "ocr_failed", "extract_failed"]);
const PENDING = new Set(["pending", "processing", "running", "queued", "in_progress"]);

export function normalizeExtractStatus(value: unknown): ExtractStatus {
  const raw = String(value ?? "pending")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  if (OK.has(raw)) return "ok";
  if (FAILED.has(raw)) return "failed";
  if (PENDING.has(raw)) return "pending";
  if (raw.includes("fail") || raw.includes("error")) return "failed";
  if (raw.includes("pend") || raw.includes("process")) return "pending";
  return "pending";
}

export function extractStatusLabel(status: ExtractStatus): string {
  if (status === "ok") return "Extracted";
  if (status === "failed") return "Extract failed";
  return "Extracting…";
}
