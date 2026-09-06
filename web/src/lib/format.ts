export function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
