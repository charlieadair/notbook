export { StudyEngine } from "./engine.js";
export type { StudyEngineOptions } from "./engine.js";
export { StudyError, topicsUnconfirmed, insufficientEvidence } from "./errors.js";
export { createStudyServer, STUDY_API_PREFIX } from "./http.js";
export { DEMO_BACKEND_PORT, DEMO_UI_PORT, STANDALONE_SMOKE_PORT } from "./ports.js";
export { MemoryStore } from "./store.js";
export {
  InMemoryVault,
  HttpVaultRetrieve,
  createFixtureVault,
  fixtureChunks,
  isCitableChunk,
  FIXTURE_NOTEBOOK_ID,
} from "./vault.js";
export { keepGroundedItems, isGroundedItem, extractSentences, buildGroundedItems } from "./quiz.js";
export { scoreTopic, buildScoreboard } from "./scoreboard.js";
export { proposeTopicNames, topicsFromNames, allTopicsConfirmed } from "./topics.js";
export type {
  Topic,
  QuizItem,
  Quiz,
  Attempt,
  TopicScore,
  Scoreboard,
  Chunk,
  VaultRetrieve,
  RetrieveArgs,
  ConfirmTopicsInput,
  GradeAttemptInput,
  GradeAttemptResult,
  GeneratedQuiz,
} from "./types.js";
export { SCORE_WINDOW, PROFICIENCY_BAR, DEFAULT_TOP_K } from "./types.js";
export type { RetrieveResponse } from "./types.js";
