import logging
from pathlib import Path
from src.schemas import PipelineState, PrincipleScore
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

def run_principles_judge(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    config = state["config"]
    survivors = state["survivors"]
    run_logger.node_start("principles_judge", n_survivors=len(survivors))

    model_slug, temperature = get_agent_config(config, "principles_judge")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_prompt = _load_prompt("principles_judge_system.md")
    user_template = _load_prompt("principles_judge_user.md")

    scores: list[PrincipleScore] = []
    for idea in survivors:
        user_prompt = user_template.format(
            idea_name=idea.name, hook_loop=idea.hook_loop,
            ai_magic_moment=idea.ai_magic_moment, user_segment=idea.user_segment,
            mvp_scope=idea.mvp_scope, ai_essential_claim=idea.ai_essential_claim,
            compounding_advantage=idea.compounding_advantage or "Not specified",
        )
        result = call_llm_structured(
            client=client, model=model_slug, temperature=temperature,
            system_prompt=system_prompt, user_prompt=user_prompt,
            schema=PrincipleScore, repair_model=repair_slug, repair_temperature=repair_temp,
        )
        run_logger.llm_call("principles_judge", model_slug, len(user_prompt), 0)
        if result:
            result.idea_id = idea.id
            scores.append(result)
            run_logger.schema_ok("principles_judge", idea.id)
        else:
            run_logger.schema_fail("principles_judge", idea.id, "Parse failed")

    run_logger.info(f"Principles Judge: scored {len(scores)}/{len(survivors)} survivors")
    run_logger.node_end("principles_judge", n_scored=len(scores))
    state["principle_scores"] = scores
    return state
