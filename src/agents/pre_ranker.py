import logging
from pathlib import Path
from src.schemas import PipelineState, PreRankerScore
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured
from src.logging_utils import RunLogger
from src.prompt_utils import format_user_context
from src.search import search_market_evidence

logger = logging.getLogger("idea_gen")
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

def run_pre_ranker(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    config = state["config"]
    survivors = state["survivors"]
    run_logger.node_start("pre_ranker", n_survivors=len(survivors))

    model_slug, temperature = get_agent_config(config, "pre_ranker")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_prompt = _load_prompt("pre_ranker_system.md")
    user_template = _load_prompt("pre_ranker_user.md")

    user_context = format_user_context(config)

    scores: list[PreRankerScore] = []
    for idea in survivors:
        # Market evidence search (graceful fallback on failure)
        evidence = search_market_evidence(
            idea_name=idea.name,
            user_segment=idea.user_segment,
            search_config=config.search,
        )
        market_block = evidence if evidence else "No market evidence available."

        user_prompt = user_template.format(
            idea_name=idea.name, hook_loop=idea.hook_loop,
            ai_magic_moment=idea.ai_magic_moment, user_segment=idea.user_segment,
            mvp_scope=idea.mvp_scope, ai_essential_claim=idea.ai_essential_claim,
            compounding_advantage=idea.compounding_advantage or "Not specified",
            user_context=user_context,
            market_evidence=market_block,
        )
        result = call_llm_structured(
            client=client, model=model_slug, temperature=temperature,
            system_prompt=system_prompt, user_prompt=user_prompt,
            schema=PreRankerScore, repair_model=repair_slug, repair_temperature=repair_temp,
        )
        run_logger.llm_call("pre_ranker", model_slug, len(user_prompt), 0)
        if result:
            result.idea_id = idea.id
            result.market_evidence = evidence
            scores.append(result)
            run_logger.schema_ok("pre_ranker", idea.id)
        else:
            run_logger.schema_fail("pre_ranker", idea.id, "Parse failed")

    run_logger.info(f"Pre-Ranker: scored {len(scores)}/{len(survivors)} survivors")
    run_logger.node_end("pre_ranker", n_scored=len(scores))
    state["pre_ranker_scores"] = scores
    return state
