import { describe, expect, it } from "vitest";
import { ApiError } from "../api/errors";
import { pretestGateMessage } from "./Topics";

describe("pretestGateMessage", () => {
  it("nudges confirm on 409 and more materials on 422", () => {
    expect(pretestGateMessage(new ApiError(409, "TopicsUnconfirmed", "x"))).toMatch(/Confirm topics/i);
    expect(pretestGateMessage(new ApiError(422, "InsufficientEvidence", "x"))).toMatch(/vault evidence/i);
    expect(pretestGateMessage(new Error("nope"))).toBeNull();
  });
});
