import { extractStatusLabel } from "../lib/extractStatus";
import type { ExtractStatus } from "../api/types";

export function ExtractBadge({ status }: { status: ExtractStatus }) {
  return <span className={`badge badge-${status}`}>{extractStatusLabel(status)}</span>;
}
