const rawBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").trim();

export const API_BASE_URL = rawBase.replace(/\/$/, "");

export const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === "1" || import.meta.env.VITE_USE_MOCK === "true";

/** Client abort for POST /sources (file + paste). Default 75s, in the 60–90s hang-UX range. */
const DEFAULT_UPLOAD_TIMEOUT_MS = 75_000;
const rawUploadTimeout = Number(import.meta.env.VITE_UPLOAD_TIMEOUT_MS);
export const UPLOAD_TIMEOUT_MS =
  Number.isFinite(rawUploadTimeout) && rawUploadTimeout > 0 ? rawUploadTimeout : DEFAULT_UPLOAD_TIMEOUT_MS;

export function joinUrl(base: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const prefix = base.endsWith("/") ? base.slice(0, -1) : base;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${prefix}${suffix}`;
}
