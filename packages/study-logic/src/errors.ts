export class StudyError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, status: number, message: string) {
    super(message);
    this.name = "StudyError";
    this.code = code;
    this.status = status;
  }

  toJSON(): { error: string; message: string } {
    return { error: this.code, message: this.message };
  }
}

export function topicsUnconfirmed(message = "Topic map is not confirmed"): StudyError {
  return new StudyError("TopicsUnconfirmed", 409, message);
}

export function insufficientEvidence(
  message = "Vault is empty or has no citable chunks",
): StudyError {
  return new StudyError("InsufficientEvidence", 422, message);
}

export function notFound(message: string): StudyError {
  return new StudyError("NotFound", 404, message);
}

export function badRequest(message: string): StudyError {
  return new StudyError("BadRequest", 400, message);
}
