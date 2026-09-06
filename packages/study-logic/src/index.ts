export { StudyEngine } from "./engine.js";
export type { StudyEngineOptions } from "./engine.js";
export { StudyError, topicsUnconfirmed, insufficientEvidence } from "./errors.js";
export { createStudyServer } from "./http.js";
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
export { SCORE_WINDOW, PROFICIENCY_BAR } from "./types.js";
