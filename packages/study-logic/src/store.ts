import type { Attempt, Quiz, QuizItem, Topic } from "./types.js";

export class MemoryStore {
  private readonly topics = new Map<string, Topic[]>();
  private readonly quizzes = new Map<string, Quiz>();
  private readonly items = new Map<string, QuizItem>();
  private readonly attempts: Attempt[] = [];

  listTopics(notebookId: string): Topic[] {
    return (this.topics.get(notebookId) ?? []).map((t) => ({ ...t }));
  }

  setTopics(notebookId: string, topics: Topic[]): void {
    this.topics.set(
      notebookId,
      topics.map((t) => ({ ...t })),
    );
  }

  putQuiz(quiz: Quiz, items: QuizItem[]): void {
    this.quizzes.set(quiz.id, { ...quiz, item_ids: [...quiz.item_ids] });
    for (const item of items) {
      this.items.set(item.id, {
        ...item,
        topic_ids: [...item.topic_ids],
        citation_chunk_ids: [...item.citation_chunk_ids],
        choices: item.choices.map((c) => ({ ...c })),
      });
    }
  }

  getQuiz(quizId: string): Quiz | undefined {
    const quiz = this.quizzes.get(quizId);
    return quiz ? { ...quiz, item_ids: [...quiz.item_ids] } : undefined;
  }

  getItem(itemId: string): QuizItem | undefined {
    const item = this.items.get(itemId);
    if (!item) return undefined;
    return {
      ...item,
      topic_ids: [...item.topic_ids],
      citation_chunk_ids: [...item.citation_chunk_ids],
      choices: item.choices.map((c) => ({ ...c })),
    };
  }

  addAttempt(attempt: Attempt): void {
    this.attempts.push({ ...attempt, topic_ids: [...attempt.topic_ids] });
  }

  listAttemptsForNotebook(notebookId: string): Attempt[] {
    return this.attempts
      .filter((a) => a.notebook_id === notebookId)
      .map((a) => ({ ...a, topic_ids: [...a.topic_ids] }));
  }
}
