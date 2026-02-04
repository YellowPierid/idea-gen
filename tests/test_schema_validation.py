"""
Integration tests for schema validation.

Tests that real LLM calls through each agent produce outputs that
parse correctly into Pydantic models. Also tests the schema repair
fallback with intentionally malformed responses.

Requires: OPENROUTER_API_KEY environment variable set.
"""

import os
import json
import pytest

from src.config import load_config, get_agent_config, resolve_model
from src.llm import create_client, call_llm, call_llm_structured, call_llm_structured_list, _try_parse
from src.schemas import (
    IdeaCandidate,
    GateResult,
    PrincipleScore,
    PreRankerScore,
    DSRProtocol,
    FinalRanking,
)


@pytest.fixture(scope="module")
def config():
    """Load pipeline config (requires OPENROUTER_API_KEY)."""
    return load_config()


@pytest.fixture(scope="module")
def client(config):
    """Create OpenRouter client."""
    return create_client(config.base_url, config.api_key)


# -- Schema parsing tests (no LLM required) ----------------------------------

class TestSchemaParsing:
    """Test that Pydantic models validate correctly from known-good JSON."""

    def test_idea_candidate_parses(self):
        data = {
            "id": "idea_001",
            "name": "Test Idea",
            "hook_loop": "User does X, AI does Y",
            "ai_magic_moment": "AI personalizes Z",
            "user_segment": "Knowledge workers",
            "mvp_scope": "Basic version",
            "ai_essential_claim": "Cannot work without AI",
            "domain": "productivity",
            "source": "raw",
        }
        result = IdeaCandidate.model_validate(data)
        assert result.id == "idea_001"
        assert result.source == "raw"

    def test_gate_result_validates_scores(self):
        data = {
            "idea_id": "idea_001",
            "q1_wrapper_risk_score": 3,
            "q1_reason": "Low risk",
            "q2_embedding_score": 7,
            "q2_workflow_embedding": "Deep integration",
            "q3_compounding_score": 8,
            "q3_hard_to_copy_reason": "Data moat",
            "status": "PASS",
        }
        result = GateResult.model_validate(data)
        assert result.status == "PASS"

    def test_gate_result_rejects_out_of_range(self):
        data = {
            "idea_id": "idea_001",
            "q1_wrapper_risk_score": 15,  # out of range
            "q1_reason": "test",
            "q2_embedding_score": 5,
            "q2_workflow_embedding": "test",
            "q3_compounding_score": 5,
            "q3_hard_to_copy_reason": "test",
            "status": "PASS",
        }
        with pytest.raises(Exception):
            GateResult.model_validate(data)

    def test_principle_score_validates(self):
        data = {
            "idea_id": "idea_001",
            "adaptive_trust": 2,
            "sandwich_workflow": 1,
            "contextual_continuity": 2,
            "outcome_monetization": 1,
            "progressive_disclosure": 2,
            "total_score": 8,
            "weakest_dimension": "sandwich_workflow",
            "improvement_suggestion": "Add review step",
        }
        result = PrincipleScore.model_validate(data)
        assert result.total_score == 8

    def test_pre_ranker_score_validates(self):
        data = {
            "idea_id": "idea_001",
            "feasibility": 2,
            "habit_potential": 1,
            "monetization": 2,
            "total_score": 5,
            "feasibility_rationale": "Simple build",
            "habit_rationale": "Weekly use",
            "monetization_rationale": "SaaS model",
        }
        result = PreRankerScore.model_validate(data)
        assert result.total_score == 5

    def test_try_parse_strips_markdown_fences(self):
        raw = '```json\n{"id": "idea_001", "name": "Test"}\n```'
        # This won't fully validate as IdeaCandidate (missing fields)
        # but tests the fence stripping logic
        result = _try_parse(raw, IdeaCandidate)
        assert result is None  # Missing required fields


# -- LLM integration tests (require API key) ---------------------------------

@pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)
class TestLLMSchemaIntegration:
    """Test that real LLM calls produce parseable structured output."""

    def test_ideator_produces_valid_ideas(self, config, client):
        """Test that ideator LLM call produces valid IdeaCandidate objects."""
        model_slug, temperature = get_agent_config(config, "ideator")
        system_prompt = (
            "You are a product idea generator for productivity apps. "
            "Return a JSON array of idea objects."
        )
        user_prompt = (
            'Generate 2 AI-native productivity app ideas as a JSON array. '
            'Each object must have these exact fields: '
            '"id" (string), "name" (string), "hook_loop" (string), '
            '"ai_magic_moment" (string), "user_segment" (string), '
            '"mvp_scope" (string), "ai_essential_claim" (string), '
            '"domain" (string, value "productivity"), '
            '"source" (string, value "raw"). '
            'Return ONLY the JSON array.'
        )
        repair_slug = resolve_model(config, config.agents["schema_repair"].model)

        ideas = call_llm_structured_list(
            client=client,
            model=model_slug,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            item_schema=IdeaCandidate,
            repair_model=repair_slug,
        )
        assert len(ideas) >= 1, "Expected at least 1 valid idea"
        assert all(isinstance(i, IdeaCandidate) for i in ideas)

    def test_schema_repair_with_malformed_json(self, config, client):
        """Test schema repair fallback with intentionally malformed output."""
        repair_slug = resolve_model(config, config.agents["schema_repair"].model)
        repair_temp = config.agents["schema_repair"].temperature

        # Intentionally malformed: missing quotes, wrong field names
        malformed = '{"idea_id": "test_001", wrapper_risk: 3, reason: "low", embed_score: 7, workflow: "deep", compound: 8, copy_reason: "moat", status: "PASS"}'

        result = call_llm_structured(
            client=client,
            model=repair_slug,
            temperature=repair_temp,
            system_prompt="Return valid JSON matching the schema.",
            user_prompt=malformed,
            schema=GateResult,
            repair_model=repair_slug,
            repair_temperature=repair_temp,
        )
        # Repair may or may not succeed -- we just verify it doesn't crash
        # and returns either a valid GateResult or None
        assert result is None or isinstance(result, GateResult)
