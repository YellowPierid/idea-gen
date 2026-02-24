"""
Pydantic v2 data models for the AI Idea Generator pipeline.

All models use ConfigDict(strict=False) to allow flexible parsing from
LLM outputs (e.g. string "7" coerced to int 7). Field validators enforce
score ranges at the boundary so downstream code can trust the data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# 1. IdeaCandidate -- raw or hybrid idea produced by the generator
# ---------------------------------------------------------------------------

class IdeaCandidate(BaseModel):
    model_config = ConfigDict(strict=False)

    id: str
    name: str
    hook_loop: str
    ai_magic_moment: str
    user_segment: str
    mvp_scope: str
    ai_essential_claim: str
    domain: str
    source: Literal["raw", "hybrid"]
    compounding_advantage: Optional[str] = None


# ---------------------------------------------------------------------------
# 2. GateResult -- gatekeeper output per idea (three questions, 0-10 each)
# ---------------------------------------------------------------------------

def _validate_0_10(value: int, field_name: str) -> int:
    if not 0 <= value <= 10:
        raise ValueError(f"{field_name} must be between 0 and 10, got {value}")
    return value


def _validate_0_2(value: int, field_name: str) -> int:
    if not 0 <= value <= 2:
        raise ValueError(f"{field_name} must be between 0 and 2, got {value}")
    return value


class GateResult(BaseModel):
    model_config = ConfigDict(strict=False)

    idea_id: str
    q1_wrapper_risk_score: int
    q1_reason: str
    q2_embedding_score: int
    q2_workflow_embedding: str
    q3_compounding_score: int
    q3_hard_to_copy_reason: str
    status: Literal["PASS", "KILL"]
    kill_reason: Optional[str] = None
    rescued: bool = False
    rescue_pivot: Optional[str] = None
    starred: bool = False

    @field_validator("q1_wrapper_risk_score")
    @classmethod
    def check_q1(cls, v: int) -> int:
        return _validate_0_10(v, "q1_wrapper_risk_score")

    @field_validator("q2_embedding_score")
    @classmethod
    def check_q2(cls, v: int) -> int:
        return _validate_0_10(v, "q2_embedding_score")

    @field_validator("q3_compounding_score")
    @classmethod
    def check_q3(cls, v: int) -> int:
        return _validate_0_10(v, "q3_compounding_score")


# ---------------------------------------------------------------------------
# 2a. AngelRescueResult -- angel's advocate sub-routine output
# ---------------------------------------------------------------------------

class AngelRescueResult(BaseModel):
    model_config = ConfigDict(strict=False)

    verdict: Literal["save", "kill"]
    pivot_feature: str
    rewritten_name: Optional[str] = None
    rewritten_hook_loop: Optional[str] = None
    rewritten_ai_magic_moment: Optional[str] = None
    rewritten_mvp_scope: Optional[str] = None
    rewritten_ai_essential_claim: Optional[str] = None
    rewritten_compounding_advantage: Optional[str] = None
    rescue_rationale: str


# ---------------------------------------------------------------------------
# 3. PrincipleScore -- five AI-native principles (0-2 each, total 0-10)
# ---------------------------------------------------------------------------

class PrincipleScore(BaseModel):
    model_config = ConfigDict(strict=False)

    idea_id: str
    adaptive_trust: int
    sandwich_workflow: int
    contextual_continuity: int
    outcome_monetization: int
    progressive_disclosure: int
    total_score: int
    weakest_dimension: str
    improvement_suggestion: str

    @field_validator(
        "adaptive_trust",
        "sandwich_workflow",
        "contextual_continuity",
        "outcome_monetization",
        "progressive_disclosure",
    )
    @classmethod
    def check_principle_range(cls, v: int, info) -> int:
        return _validate_0_2(v, info.field_name)

    @field_validator("total_score")
    @classmethod
    def check_total(cls, v: int) -> int:
        return _validate_0_10(v, "total_score")


# ---------------------------------------------------------------------------
# 4. PreRankerScore -- feasibility / habit / monetization (0-2 each, 0-6)
# ---------------------------------------------------------------------------

class PreRankerScore(BaseModel):
    model_config = ConfigDict(strict=False)

    idea_id: str
    feasibility: int
    habit_potential: int
    monetization: int
    total_score: int
    feasibility_rationale: str
    habit_rationale: str
    monetization_rationale: str
    market_evidence: Optional[str] = None

    @field_validator("feasibility", "habit_potential", "monetization")
    @classmethod
    def check_sub_range(cls, v: int, info) -> int:
        return _validate_0_2(v, info.field_name)

    @field_validator("total_score")
    @classmethod
    def check_pre_ranker_total(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError(f"total_score must be between 0 and 6, got {v}")
        return v


# ---------------------------------------------------------------------------
# 5. ReservationTest + DSRProtocol
# ---------------------------------------------------------------------------

class ReservationTest(BaseModel):
    model_config = ConfigDict(strict=False)

    offer_description: str
    target_persona: str
    headline: str
    value_proposition: str
    conversion_drivers: List[str]
    anticipated_objections: List[str]


class DSRProtocol(BaseModel):
    model_config = ConfigDict(strict=False)

    idea_id: str
    problem_framing: str
    assumptions: List[str]
    woz_test_steps: List[str]
    hook_metrics: Dict[str, str]
    reservation_test: ReservationTest
    trust_breakers: List[str]
    falsification_criteria: str

    @field_validator("woz_test_steps")
    @classmethod
    def check_woz_steps(cls, v: List[str]) -> List[str]:
        if len(v) != 3:
            raise ValueError(
                f"woz_test_steps must contain exactly 3 steps, got {len(v)}"
            )
        return v

    @field_validator("hook_metrics")
    @classmethod
    def check_hook_metrics(cls, v: Dict[str, str]) -> Dict[str, str]:
        required_keys = {"activation", "repeated_use", "reliance_ratio"}
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(f"hook_metrics missing required keys: {missing}")
        return v

    @field_validator("trust_breakers")
    @classmethod
    def check_trust_breakers(cls, v: List[str]) -> List[str]:
        if len(v) != 3:
            raise ValueError(
                f"trust_breakers must contain exactly 3 items, got {len(v)}"
            )
        return v


# ---------------------------------------------------------------------------
# 6. FinalRanking
# ---------------------------------------------------------------------------

class FinalRanking(BaseModel):
    model_config = ConfigDict(strict=False)

    rank: int
    idea_id: str
    idea_name: str
    total_score: float
    rationale: str
    gate_status: Literal["PASS"]
    principle_score: int
    feasibility_score: int
    habit_score: int
    monetization_score: int

    @field_validator("principle_score")
    @classmethod
    def check_principle(cls, v: int) -> int:
        return _validate_0_10(v, "principle_score")

    @field_validator("feasibility_score", "habit_score", "monetization_score")
    @classmethod
    def check_final_sub(cls, v: int, info) -> int:
        return _validate_0_2(v, info.field_name)


# ---------------------------------------------------------------------------
# 7. PipelineConfig and sub-configs
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    model: str
    temperature: float


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    provider: str
    model: str
    fallback: str


class GatekeeperConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    q1_kill_threshold: int
    q2_kill_threshold: int
    q3_kill_threshold: int


class PipelineParams(BaseModel):
    model_config = ConfigDict(strict=False)

    domain: str
    android_profile: str = ""
    n_raw: int
    top_k: int
    min_hybrids: int
    max_retries: int
    seed: int


class UserProfile(BaseModel):
    model_config = ConfigDict(strict=False)

    skills: List[str] = []
    stack: List[str] = []
    past_projects: List[str] = []


class SearchConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    enabled: bool = False
    provider: str = "duckduckgo"
    max_results: int = 3
    timeout_seconds: int = 10


class MemoryConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    similarity_threshold: float = 0.85
    history_dir: str = "./outputs/global_history"


class PipelineConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    base_url: str
    api_key: str
    models: Dict[str, str]
    agents: Dict[str, AgentConfig]
    embedding: EmbeddingConfig
    gatekeeper: GatekeeperConfig
    pipeline: PipelineParams
    output_dir: str
    user_profile: Optional[UserProfile] = None
    search: SearchConfig = SearchConfig()
    memory: MemoryConfig = MemoryConfig()


# ---------------------------------------------------------------------------
# 8. CheckpointData
# ---------------------------------------------------------------------------

class CheckpointData(BaseModel):
    model_config = ConfigDict(strict=False)

    last_completed_node: str
    timestamp: str
    state: Dict[str, Any]


# ---------------------------------------------------------------------------
# 9. PipelineState -- TypedDict for LangGraph-style state passing
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    config: PipelineConfig
    android_profile: str
    raw_ideas: List[IdeaCandidate]
    selected_ideas: List[IdeaCandidate]
    hybrids: List[IdeaCandidate]
    all_candidates: List[IdeaCandidate]
    gate_results: List[GateResult]
    survivors: List[IdeaCandidate]
    principle_scores: List[PrincipleScore]
    pre_ranker_scores: List[PreRankerScore]
    dsr_protocols: List[DSRProtocol]
    final_ranking: List[FinalRanking]
    retry_count: int
    starred_ids: List[str]
    interactive: bool
