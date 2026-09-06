import { describe, expect, it } from "vitest";
import { ApiError } from "../api/errors";
import { sourceUploadFeedback, UPLOAD_HANG_MESSAGE, uploadFailureMessage } from "./upload";

describe("uploadFailureMessage", () => {
  it("maps abort, timeout, and network errors to one retry line", () => {
    expect(uploadFailureMessage(new DOMException("The operation was aborted.", "AbortError"))).toBe(
      UPLOAD_HANG_MESSAGE,
    );
    expect(uploadFailureMessage(new ApiError(408, "UploadTimeout", "x"))).toBe(UPLOAD_HANG_MESSAGE);
    expect(uploadFailureMessage(new TypeError("Failed to fetch"))).toBe(UPLOAD_HANG_MESSAGE);
  });

  it("prefers Backend extract_status / extract_error when the body has them", () => {
    expect(
      uploadFailureMessage(
        new ApiError(500, "HTTP_500", "Request failed (500)", {
          extract_status: "failed",
          extract_error: "PDF extract timed out on this file.",
        }),
      ),
    ).toBe("PDF extract timed out on this file.");
    expect(
      uploadFailureMessage(
        new ApiError(422, "HTTP_422", "Request failed (422)", { extract_status: "failed" }),
      ),
    ).toMatch(/Extract failed/i);
    expect(
      uploadFailureMessage(new ApiError(400, "BadRequest", "File too large")),
    ).toBe("File too large");
  });
});

describe("sourceUploadFeedback", () => {
  it("surfaces extract_status failed instead of a success note", () => {
    expect(
      sourceUploadFeedback({
        id: "s1",
        filename: "lec1-notes.pdf",
        extract_status: "failed",
        chunk_count: 0,
        extract_error: "PDF extract timed out",
      }),
    ).toEqual({ error: "PDF extract timed out", note: null });
    expect(
      sourceUploadFeedback({
        id: "s2",
        filename: "ok.pdf",
        extract_status: "ok",
        chunk_count: 2,
      }),
    ).toEqual({ error: null, note: "Added ok.pdf." });
  });
});
