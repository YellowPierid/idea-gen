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

    protocols: list[DSRProtocol] = []
    for idea in survivors:
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
        result = call_llm_structured(
            client=client, model=model_slug, temperature=temperature,
            system_prompt=system_prompt, user_prompt=user_prompt,
            schema=DSRProtocol, repair_model=repair_slug, repair_temperature=repair_temp,
        )
        run_logger.llm_call("dsr_designer", model_slug, len(user_prompt), 0)
        if result:
            result.idea_id = idea.id
            protocols.append(result)
            run_logger.schema_ok("dsr_designer", idea.id)
        else:
            run_logger.schema_fail("dsr_designer", idea.id, "Parse failed")

    run_logger.info(f"DSR Designer: created {len(protocols)}/{len(survivors)} protocols")
    run_logger.node_end("dsr_designer", n_protocols=len(protocols))
    state["dsr_protocols"] = protocols
    return state
