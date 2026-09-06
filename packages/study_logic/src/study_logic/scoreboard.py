from __future__ import annotations

from datetime import datetime, timezone

from study_logic.models import (
    PROFICIENCY_BAR,
    SCORE_WINDOW,
    SEVERE_MISS_COUNT,
    SEVERE_RATE,
    Attempt,
    Scoreboard,
    Topic,
    TopicScore,
)


def score_topic(notebook_id: str, topic_id: str, attempts: list[Attempt], now: str | None = None) -> TopicScore:
    updated = now or datetime.now(timezone.utc).isoformat()
    windowed = [a for a in attempts if topic_id in a.topic_ids][-SCORE_WINDOW:]
    attempt_count = len(windowed)
    correct_count = sum(1 for a in windowed if a.correct)
    miss_count = attempt_count - correct_count
    correct_rate = 0.0 if attempt_count == 0 else correct_count / attempt_count
    proficient = attempt_count > 0 and correct_rate >= PROFICIENCY_BAR
    severity = "ok"
    if attempt_count > 0:
        if correct_rate < SEVERE_RATE or miss_count >= SEVERE_MISS_COUNT:
            severity = "severe"
        elif not proficient:
            severity = "mild"
    return TopicScore(
        topic_id=topic_id,
        notebook_id=notebook_id,
        correct_count=correct_count,
        attempt_count=attempt_count,
        correct_rate=correct_rate,
        proficient=proficient,
        severity=severity,
        updated_at=updated,
    )


def build_scoreboard(notebook_id: str, topics: list[Topic], attempts: list[Attempt]) -> Scoreboard:
    now = datetime.now(timezone.utc).isoformat()
    return Scoreboard(
        topics=[score_topic(notebook_id, topic.id, attempts, now) for topic in topics],
        window=SCORE_WINDOW,
        proficiency_bar=PROFICIENCY_BAR,
    )
