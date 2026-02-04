import json
import logging
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from typing import List
from src.schemas import PipelineState, FinalRanking
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured
from src.scoring import compute_final_score
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


class RankerLLMResponse(BaseModel):
    """LLM response schema for the ranker (rationales + 7-day plan)."""
    model_config = ConfigDict(strict=False)
    rankings: List[dict]  # each has idea_id, idea_name, rationale
    seven_day_plan: str
    notes: str


def run_ranker(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    config = state["config"]
    survivors = state["survivors"]
    principle_scores = {s.idea_id: s for s in state["principle_scores"]}
    pre_ranker_scores = {s.idea_id: s for s in state["pre_ranker_scores"]}

    run_logger.node_start("ranker", n_survivors=len(survivors))

    # Step 1: Compute final scores
    scored_ideas = []
    for idea in survivors:
        ps = principle_scores.get(idea.id)
        pr = pre_ranker_scores.get(idea.id)
        if not ps or not pr:
            continue

        final_score = compute_final_score(
            principle_score=ps.total_score,
            feasibility=pr.feasibility,
            habit=pr.habit_potential,
            monetization=pr.monetization,
        )
        scored_ideas.append({
            "idea": idea,
            "principle_score": ps.total_score,
            "feasibility": pr.feasibility,
            "habit": pr.habit_potential,
            "monetization": pr.monetization,
            "final_score": final_score,
        })

    # Sort by final_score descending
    scored_ideas.sort(key=lambda x: x["final_score"], reverse=True)

    # Step 2: Build summary for LLM
    ideas_summary = []
    for rank, item in enumerate(scored_ideas, 1):
        idea = item["idea"]
        ideas_summary.append({
            "rank": rank,
            "idea_id": idea.id,
            "idea_name": idea.name,
            "hook_loop": idea.hook_loop,
            "ai_magic_moment": idea.ai_magic_moment,
            "mvp_scope": idea.mvp_scope,
            "final_score": round(item["final_score"], 3),
            "principle_score": item["principle_score"],
            "feasibility": item["feasibility"],
            "habit": item["habit"],
            "monetization": item["monetization"],
        })

    # Step 3: Call LLM for rationales and 7-day plan
    model_slug, temperature = get_agent_config(config, "ranker")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_prompt = _load_prompt("ranker_system.md")
    user_template = _load_prompt("ranker_user.md")
    user_prompt = user_template.format(
        domain=config.pipeline.domain,
        ideas_with_scores=json.dumps(ideas_summary, indent=2),
        n_survivors=len(scored_ideas),
    )

    llm_response = call_llm_structured(
        client=client, model=model_slug, temperature=temperature,
        system_prompt=system_prompt, user_prompt=user_prompt,
        schema=RankerLLMResponse, repair_model=repair_slug, repair_temperature=repair_temp,
    )
    run_logger.llm_call("ranker", model_slug, len(user_prompt), 0)

    # Step 4: Build FinalRanking objects
    rationales = {}
    seven_day_plan = ""
    notes = ""
    if llm_response:
        for r in llm_response.rankings:
            rationales[r.get("idea_id", "")] = r.get("rationale", "")
        seven_day_plan = llm_response.seven_day_plan
        notes = llm_response.notes

    final_ranking: list[FinalRanking] = []
    for rank, item in enumerate(scored_ideas, 1):
        idea = item["idea"]
        final_ranking.append(FinalRanking(
            rank=rank,
            idea_id=idea.id,
            idea_name=idea.name,
            total_score=round(item["final_score"], 3),
            rationale=rationales.get(idea.id, "No rationale available"),
            gate_status="PASS",
            principle_score=item["principle_score"],
            feasibility_score=item["feasibility"],
            habit_score=item["habit"],
            monetization_score=item["monetization"],
        ))

    run_logger.info(f"Ranker: ranked {len(final_ranking)} ideas")
    run_logger.node_end("ranker", n_ranked=len(final_ranking))

    state["final_ranking"] = final_ranking
    # Store the 7-day plan and notes in state for output generation
    state["_seven_day_plan"] = seven_day_plan
    state["_ranker_notes"] = notes
    return state
