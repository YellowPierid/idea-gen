"""
Integration tests for gatekeeper threshold logic.

Tests that the gatekeeper correctly applies PASS/KILL thresholds
based on structured scoring. Also tests edge cases.

Requires: OPENROUTER_API_KEY environment variable for LLM tests.
"""

import os
import pytest

from src.scoring import apply_gate_thresholds
from src.schemas import GateResult


class TestGatekeeperThresholds:
    """Test programmatic kill threshold logic (no LLM needed)."""

    def test_all_pass(self):
        """Idea with good scores passes all thresholds."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=2,   # low wrapper risk (good)
            embedding_score=8,      # strong embedding (good)
            compounding_score=7,    # strong moat (good)
        )
        assert status == "PASS"
        assert reason is None

    def test_kill_high_wrapper_risk(self):
        """Q1: wrapper_risk >= 6 should KILL."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=6,   # too wrapper-like
            embedding_score=8,
            compounding_score=7,
        )
        assert status == "KILL"
        assert "wrapper_risk_score=6" in reason

    def test_kill_weak_embedding(self):
        """Q2: embedding_score <= 3 should KILL."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=2,
            embedding_score=3,      # too weak
            compounding_score=7,
        )
        assert status == "KILL"
        assert "embedding_score=3" in reason

    def test_kill_weak_compounding(self):
        """Q3: compounding_score <= 3 should KILL."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=2,
            embedding_score=8,
            compounding_score=3,    # no moat
        )
        assert status == "KILL"
        assert "compounding_score=3" in reason

    def test_multiple_kills_all_reasons(self):
        """Multiple threshold violations should all be reported."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=8,
            embedding_score=2,
            compounding_score=1,
        )
        assert status == "KILL"
        assert "wrapper_risk_score=8" in reason
        assert "embedding_score=2" in reason
        assert "compounding_score=1" in reason

    def test_edge_case_q1_threshold_minus_one(self):
        """Q1 score just below threshold should PASS."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=5,   # below 6
            embedding_score=8,
            compounding_score=7,
        )
        assert status == "PASS"

    def test_edge_case_q2_threshold_plus_one(self):
        """Q2 score just above threshold should PASS."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=2,
            embedding_score=4,      # above 3
            compounding_score=7,
        )
        assert status == "PASS"

    def test_edge_case_q3_threshold_plus_one(self):
        """Q3 score just above threshold should PASS."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=2,
            embedding_score=8,
            compounding_score=4,    # above 3
        )
        assert status == "PASS"

    def test_custom_thresholds(self):
        """Test with custom (less strict) thresholds."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=7,
            embedding_score=2,
            compounding_score=2,
            q1_threshold=8,   # more lenient
            q2_threshold=1,   # more lenient
            q3_threshold=1,   # more lenient
        )
        assert status == "PASS"

    def test_custom_thresholds_strict(self):
        """Test with stricter-than-default thresholds."""
        status, reason = apply_gate_thresholds(
            wrapper_risk_score=4,
            embedding_score=5,
            compounding_score=5,
            q1_threshold=4,   # stricter
            q2_threshold=5,   # stricter
            q3_threshold=5,   # stricter
        )
        assert status == "KILL"


@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)
class TestGatekeeperLLMIntegration:
    """Test gatekeeper with real LLM calls on known ideas."""

    def test_obvious_wrapper_gets_killed(self):
        """An obvious ChatGPT wrapper should be killed."""
        from src.config import load_config, get_agent_config, resolve_model
        from src.llm import create_client, call_llm_structured
        from src.agents.gatekeeper import GateLLMResponse

        config = load_config()
        model_slug, temp = get_agent_config(config, "gatekeeper")
        repair_slug = resolve_model(config, config.agents["schema_repair"].model)
        client = create_client(config.base_url, config.api_key)

        system_prompt = (
            "You evaluate AI app ideas for wrapper risk. Return a JSON object with: "
            '"idea_id", "q1_wrapper_risk_score" (0-10), "q1_reason", '
            '"q2_embedding_score" (0-10), "q2_workflow_embedding", '
            '"q3_compounding_score" (0-10), "q3_hard_to_copy_reason". '
            "Be strict."
        )
        # Obvious wrapper: just a ChatGPT UI skin
        user_prompt = (
            'Evaluate: Name="ChatGPT But Pretty", '
            'Hook Loop="User types question, gets answer", '
            'AI Magic Moment="Nice UI for ChatGPT responses", '
            'MVP Scope="Chat interface with OpenAI API", '
            'AI-Essential Claim="Uses GPT to answer questions", '
            'Compounding Advantage="None"'
        )

        result = call_llm_structured(
            client=client, model=model_slug, temperature=temp,
            system_prompt=system_prompt, user_prompt=user_prompt,
            schema=GateLLMResponse, repair_model=repair_slug,
        )

        if result is not None:
            status, reason = apply_gate_thresholds(
                result.q1_wrapper_risk_score,
                result.q2_embedding_score,
                result.q3_compounding_score,
            )
            # An obvious wrapper should be killed
            assert status == "KILL", (
                f"Expected KILL for obvious wrapper, got PASS. "
                f"Scores: q1={result.q1_wrapper_risk_score}, "
                f"q2={result.q2_embedding_score}, q3={result.q3_compounding_score}"
            )
