import { randomUUID } from "node:crypto";
import { badRequest, insufficientEvidence, notFound, topicsUnconfirmed } from "./errors.js";
import { buildGroundedItems, createQuizRecord } from "./quiz.js";
import { buildScoreboard, scoreTopic } from "./scoreboard.js";
import { MemoryStore } from "./store.js";
import { allTopicsConfirmed, proposeTopicNames, topicsFromNames } from "./topics.js";
import type {
  ConfirmTopicsInput,
  GeneratedQuiz,
  GradeAttemptInput,
  GradeAttemptResult,
  Scoreboard,
  Topic,
  TopicScore,
  VaultRetrieve,
} from "./types.js";
import { isCitableChunk } from "./vault.js";

export type StudyEngineOptions = {
  vault: VaultRetrieve;
  store?: MemoryStore;
};

export class StudyEngine {
  readonly store: MemoryStore;
  private readonly vault: VaultRetrieve;

  constructor(options: StudyEngineOptions) {
    this.vault = options.vault;
    this.store = options.store ?? new MemoryStore();
  }

  async proposeTopics(notebookId: string): Promise<Topic[]> {
    const chunks = await this.vault.retrieve({
      notebook_id: notebookId,
      query: "",
      top_k: 50,
    });
    const names = proposeTopicNames(chunks.filter(isCitableChunk));
    const topics = topicsFromNames(notebookId, names, false);
    this.store.setTopics(notebookId, topics);
    return topics;
  }

  confirmTopics(notebookId: string, input: ConfirmTopicsInput = {}): Topic[] {
    if (input.names && input.names.length > 0) {
      const topics = topicsFromNames(notebookId, input.names, true);
      this.store.setTopics(notebookId, topics);
      return topics;
    }

    const existing = this.store.listTopics(notebookId);
    const allow = input.topic_ids?.length ? new Set(input.topic_ids) : null;
    const updated = existing.map((topic) => ({
      ...topic,
      confirmed: allow ? allow.has(topic.id) || topic.confirmed : true,
    }));
    this.store.setTopics(notebookId, updated);
    return updated;
  }

  listTopics(notebookId: string): Topic[] {
    return this.store.listTopics(notebookId);
  }

  async createQuiz(notebookId: string): Promise<GeneratedQuiz> {
    const topics = this.store.listTopics(notebookId);
    if (!allTopicsConfirmed(topics)) {
      throw topicsUnconfirmed("Confirm every topic before generating a quiz");
    }

    const evidence = new Map<string, Awaited<ReturnType<VaultRetrieve["retrieve"]>>>();
    const knownIds = new Set<string>();

    for (const topic of topics) {
      const chunks = (await this.vault.retrieve({
        notebook_id: notebookId,
        query: topic.name,
        top_k: 8,
      })).filter(isCitableChunk);
      evidence.set(topic.id, chunks);
      for (const chunk of chunks) knownIds.add(chunk.id);
    }

    if (knownIds.size === 0) {
      throw insufficientEvidence("Vault is empty or returned no citable chunks");
    }

    const quizId = randomUUID();
    const items = buildGroundedItems({ quizId, topics, evidence });
    if (items.length === 0) {
      throw insufficientEvidence("No grounded quiz items could be built from retrieved chunks");
    }

    const quiz = createQuizRecord(notebookId, items);
    this.store.putQuiz(quiz, items);
    return { quiz, items };
  }

  gradeAttempt(quizId: string, input: GradeAttemptInput): GradeAttemptResult {
    if (!input.item_id || !input.selected_choice_id) {
      throw badRequest("item_id and selected_choice_id are required");
    }

    const quiz = this.store.getQuiz(quizId);
    if (!quiz) throw notFound(`Quiz not found: ${quizId}`);

    const item = this.store.getItem(input.item_id);
    if (!item || item.quiz_id !== quizId) {
      throw notFound(`Quiz item not found: ${input.item_id}`);
    }

    const attempt = {
      id: randomUUID(),
      item_id: item.id,
      quiz_id: quiz.id,
      notebook_id: quiz.notebook_id,
      selected_choice_id: input.selected_choice_id,
      correct: input.selected_choice_id === item.correct_choice_id,
      topic_ids: [...item.topic_ids],
      created_at: new Date().toISOString(),
    };

    this.store.addAttempt(attempt);
    const attempts = this.store.listAttemptsForNotebook(quiz.notebook_id);
    const now = attempt.created_at;
    const scores: TopicScore[] = item.topic_ids.map((topicId) =>
      scoreTopic(quiz.notebook_id, topicId, attempts, now),
    );

    return { attempt, scores };
  }

  scoreboard(notebookId: string): Scoreboard {
    return buildScoreboard(
      notebookId,
      this.store.listTopics(notebookId),
      this.store.listAttemptsForNotebook(notebookId),
    );
  }
}
