"""Scoring utilities for the idea-generation pipeline."""

from typing import Literal


def apply_gate_thresholds(
    wrapper_risk_score: int,
    embedding_score: int,
    compounding_score: int,
    q1_threshold: int = 6,
    q2_threshold: int = 3,
    q3_threshold: int = 3,
) -> tuple[Literal["PASS", "KILL"], str | None]:
    """Apply gatekeeper kill thresholds. Returns (status, kill_reason)."""
    reasons = []

    if wrapper_risk_score >= q1_threshold:
        reasons.append(
            f"wrapper_risk_score={wrapper_risk_score} >= {q1_threshold} "
            "(too much overlap with generic ChatGPT)"
        )

    if embedding_score <= q2_threshold:
        reasons.append(
            f"embedding_score={embedding_score} <= {q2_threshold} "
            "(weak workflow integration)"
        )

    if compounding_score <= q3_threshold:
        reasons.append(
            f"compounding_score={compounding_score} <= {q3_threshold} "
            "(no real moat)"
        )

    if reasons:
        return "KILL", "; ".join(reasons)
    return "PASS", None


def normalize_scores(
    principle_score: int,
    feasibility: int,
    habit: int,
    monetization: int,
) -> dict[str, float]:
    """Normalize all scores to 0-1 range."""
    return {
        "principle": principle_score / 10.0,
        "feasibility": feasibility / 2.0,
        "habit": habit / 2.0,
        "monetization": monetization / 2.0,
    }


def compute_final_score(
    principle_score: int,
    feasibility: int,
    habit: int,
    monetization: int,
) -> float:
    """Compute final aggregate score with equal weights.

    All scores normalized to 0-1, then summed. Range: 0-4.
    """
    normalized = normalize_scores(principle_score, feasibility, habit, monetization)
    return sum(normalized.values())
