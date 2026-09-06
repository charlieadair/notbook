from __future__ import annotations

from study_logic.models import (
    MAX_SPAWN,
    SEVERE_RATE,
    Chat,
    Scoreboard,
    SpawnCandidate,
    SpawnOffer,
    Topic,
    TopicScore,
)


def candidate_reason(score: TopicScore, name: str) -> str:
    rate_pct = round(score.correct_rate * 100)
    miss_count = score.attempt_count - score.correct_count
    if score.severity == "severe":
        if score.correct_rate < SEVERE_RATE:
            return (
                f"{name}: severe gap — {score.correct_count}/{score.attempt_count} "
                f"({rate_pct}%) below {int(SEVERE_RATE * 100)}%."
            )
        return f"{name}: severe gap — {miss_count} misses in the recent window."
    return (
        f"{name}: mild gap — {score.correct_count}/{score.attempt_count} "
        f"({rate_pct}%) below the 80% bar; stays on the scoreboard."
    )


def _gap_sort_key(score: TopicScore) -> tuple[int, float, int, str]:
    # Severe first, then lower rate, then more misses, then stable id.
    rank = 0 if score.severity == "severe" else 1
    misses = score.attempt_count - score.correct_count
    return (rank, score.correct_rate, -misses, score.topic_id)


def build_spawn_offer(notebook_id: str, topics: list[Topic], board: Scoreboard) -> SpawnOffer:
    """Rank mild/severe gaps. Caller must skip this when the notebook has no attempts."""
    names = {topic.id: topic.name for topic in topics}
    gaps = [row for row in board.topics if row.severity in ("mild", "severe")]
    gaps.sort(key=_gap_sort_key)
    candidates = [
        SpawnCandidate(
            topic_id=row.topic_id,
            severity=row.severity,
            reason=candidate_reason(row, names.get(row.topic_id, row.topic_id)),
        )
        for row in gaps[:MAX_SPAWN]
    ]
    return SpawnOffer(notebook_id=notebook_id, candidates=candidates, max_spawn=MAX_SPAWN)


def build_handoff_summary(chat: Chat, topics: list[Topic], board: Scoreboard) -> str:
    """Progress snapshot only — no unsourced teaching claims (those would need chunk cites)."""
    names = {topic.id: topic.name for topic in topics}
    focused = [names.get(topic_id, topic_id) for topic_id in chat.topic_ids]
    focus = ", ".join(focused) if focused else "this focus chat"
    parts = [f"Closed specialist chat on {focus}."]
    rows = [row for row in board.topics if row.severity in ("mild", "severe")]
    if rows:
        bits = [
            f"{names.get(row.topic_id, row.topic_id)} {row.severity} "
            f"({row.correct_count}/{row.attempt_count})"
            for row in rows
        ]
        parts.append("Scoreboard: " + "; ".join(bits) + ".")
    else:
        parts.append("Scoreboard has no remaining mild or severe gaps.")
    return " ".join(parts)
