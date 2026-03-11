import asyncio
import logging
from pathlib import Path
from src.schemas import PipelineState, DSRProtocol
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


async def _design_one(
    idea,
    principle_scores: dict,
    pre_ranker_scores: dict,
    user_template: str,
    system_prompt: str,
    client,
    model_slug: str,
    temperature: float,
    repair_slug: str,
    repair_temp: float,
    run_logger: RunLogger,
) -> DSRProtocol | None:
    ps = principle_scores.get(idea.id)
    pr = pre_ranker_scores.get(idea.id)
    user_prompt = user_template.format(
        idea_name=idea.name, hook_loop=idea.hook_loop,
        ai_magic_moment=idea.ai_magic_moment, user_segment=idea.user_segment,
        mvp_scope=idea.mvp_scope, ai_essential_claim=idea.ai_essential_claim,
        compounding_advantage=idea.compounding_advantage or "Not specified",
        principle_score=ps.total_score if ps else 0,
        feasibility=pr.feasibility if pr else 0,
        habit=pr.habit_potential if pr else 0,
        monetization=pr.monetization if pr else 0,
    )
    result = await asyncio.to_thread(
        call_llm_structured,
        client=client, model=model_slug, temperature=temperature,
        system_prompt=system_prompt, user_prompt=user_prompt,
        schema=DSRProtocol, repair_model=repair_slug, repair_temperature=repair_temp,
    )
    run_logger.llm_call("dsr_designer", model_slug, len(user_prompt), 0)
    if result:
        result.idea_id = idea.id
        run_logger.schema_ok("dsr_designer", idea.id)
        return result
    run_logger.schema_fail("dsr_designer", idea.id, "Parse failed")
    return None


def run_dsr_designer(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    config = state["config"]
    survivors = state["survivors"]
    principle_scores = {s.idea_id: s for s in state["principle_scores"]}
    pre_ranker_scores = {s.idea_id: s for s in state["pre_ranker_scores"]}

    run_logger.node_start("dsr_designer", n_survivors=len(survivors))

    model_slug, temperature = get_agent_config(config, "dsr_designer")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_prompt = _load_prompt("dsr_designer_system.md")
    user_template = _load_prompt("dsr_designer_user.md")

    async def _run_all():
        return await asyncio.gather(*[
            _design_one(
                idea, principle_scores, pre_ranker_scores,
                user_template, system_prompt, client,
                model_slug, temperature, repair_slug, repair_temp, run_logger
            )
            for idea in survivors
        ])

    raw_results = asyncio.run(_run_all())
    protocols = [r for r in raw_results if r is not None]

    run_logger.info(f"DSR Designer: created {len(protocols)}/{len(survivors)} protocols")
    run_logger.node_end("dsr_designer", n_protocols=len(protocols))
    state["dsr_protocols"] = protocols
    return state
