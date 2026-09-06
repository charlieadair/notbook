const rawBase = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1").trim();

export const API_BASE_URL = rawBase.replace(/\/$/, "");

export const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === "1" || import.meta.env.VITE_USE_MOCK === "true";

export function joinUrl(base: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const prefix = base.endsWith("/") ? base.slice(0, -1) : base;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${prefix}${suffix}`;
}
