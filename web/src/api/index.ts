import { USE_MOCK } from "../lib/config";
import { HttpStudyApi } from "./client";
import { MockStudyApi } from "./mock";
import type { StudyApi } from "./types";

export function createStudyApi(): StudyApi {
  if (USE_MOCK) return new MockStudyApi();
  return new HttpStudyApi();
}

export type { StudyApi } from "./types";
