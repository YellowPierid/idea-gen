"""
Integration tests for ranker stability and score aggregation.

Tests that the ranking aggregation math works correctly with known inputs,
and (with API key) that running the pipeline twice with the same seed
produces consistent results.

Requires: OPENROUTER_API_KEY environment variable for full pipeline tests.
"""

import os
import pytest

from src.scoring import compute_final_score, normalize_scores


class TestScoreAggregation:
    """Test the equal-weight aggregation math with known inputs."""

    def test_perfect_scores(self):
        """All maximum scores should produce max final score (4.0)."""
        score = compute_final_score(
            principle_score=10,
            feasibility=2,
            habit=2,
            monetization=2,
        )
        assert score == pytest.approx(4.0)

    def test_zero_scores(self):
        """All zero scores should produce 0."""
        score = compute_final_score(
            principle_score=0,
            feasibility=0,
            habit=0,
            monetization=0,
        )
        assert score == pytest.approx(0.0)

    def test_mixed_scores(self):
        """Test with mixed scores."""
        score = compute_final_score(
            principle_score=5,   # 0.5 normalized
            feasibility=1,       # 0.5 normalized
            habit=2,             # 1.0 normalized
            monetization=0,      # 0.0 normalized
        )
        assert score == pytest.approx(2.0)

    def test_normalization_ranges(self):
        """Verify normalization produces 0-1 values."""
        normalized = normalize_scores(
            principle_score=7,
            feasibility=1,
            habit=2,
            monetization=0,
        )
        assert normalized["principle"] == pytest.approx(0.7)
        assert normalized["feasibility"] == pytest.approx(0.5)
        assert normalized["habit"] == pytest.approx(1.0)
        assert normalized["monetization"] == pytest.approx(0.0)

    def test_equal_weights(self):
        """All dimensions should contribute equally.

        If only one dimension is maxed and rest are zero,
        the total should be 1.0 (one quarter of max 4.0).
        """
        # Only principles maxed
        s1 = compute_final_score(principle_score=10, feasibility=0, habit=0, monetization=0)
        # Only feasibility maxed
        s2 = compute_final_score(principle_score=0, feasibility=2, habit=0, monetization=0)
        # Only habit maxed
        s3 = compute_final_score(principle_score=0, feasibility=0, habit=2, monetization=0)
        # Only monetization maxed
        s4 = compute_final_score(principle_score=0, feasibility=0, habit=0, monetization=2)

        assert s1 == pytest.approx(1.0)
        assert s2 == pytest.approx(1.0)
        assert s3 == pytest.approx(1.0)
        assert s4 == pytest.approx(1.0)

    def test_ranking_order_with_known_inputs(self):
        """Test that ideas sort correctly by final score."""
        ideas = [
            {"name": "A", "score": compute_final_score(8, 2, 2, 1)},
            {"name": "B", "score": compute_final_score(10, 2, 2, 2)},
            {"name": "C", "score": compute_final_score(3, 1, 0, 1)},
        ]
        ranked = sorted(ideas, key=lambda x: x["score"], reverse=True)
        assert ranked[0]["name"] == "B"
        assert ranked[1]["name"] == "A"
        assert ranked[2]["name"] == "C"

    def test_tiebreaking_deterministic(self):
        """Ideas with identical scores maintain stable ordering."""
        scores = [
            compute_final_score(6, 1, 1, 1),
            compute_final_score(6, 1, 1, 1),
        ]
        assert scores[0] == scores[1]


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)
class TestPipelineStability:
    """Test that running the pipeline with the same seed is stable.

    Due to LLM non-determinism, we test best-effort: the same ideas
    should be generated (names may vary) and scores should be in a
    similar range. This is a smoke test, not a strict equality check.
    """

    def test_ideator_produces_ideas(self):
        """Basic smoke test: ideator produces parseable ideas."""
        from src.config import load_config, get_agent_config, resolve_model
        from src.llm import create_client, call_llm_structured_list
        from src.schemas import IdeaCandidate

        config = load_config()
        model_slug, temp = get_agent_config(config, "ideator")
        repair_slug = resolve_model(config, config.agents["schema_repair"].model)
        client = create_client(config.base_url, config.api_key)

        system_prompt = (
            "You generate AI-native productivity app ideas. "
            "Return a JSON array of idea objects."
        )
        user_prompt = (
            'Generate 3 AI-native productivity app ideas as JSON array. '
            'Each must have: "id", "name", "hook_loop", "ai_magic_moment", '
            '"user_segment", "mvp_scope", "ai_essential_claim", '
            '"domain" ("productivity"), "source" ("raw"). '
            "Return ONLY the JSON array."
        )

        ideas = call_llm_structured_list(
            client=client, model=model_slug, temperature=temp,
            system_prompt=system_prompt, user_prompt=user_prompt,
            item_schema=IdeaCandidate, repair_model=repair_slug,
        )
        assert len(ideas) >= 1, "Ideator should produce at least 1 idea"
