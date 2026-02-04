import json
import logging
from pathlib import Path
from src.schemas import PipelineState, IdeaCandidate
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured_list
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _ideas_to_json(ideas: list[IdeaCandidate]) -> str:
    """Serialize ideas to JSON string for the prompt."""
    return json.dumps([idea.model_dump() for idea in ideas], indent=2)


def run_recombiner(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Node B: Combine selected ideas into hybrids (min 5)."""
    config = state["config"]
    selected = state["selected_ideas"]
    domain = config.pipeline.domain
    min_hybrids = config.pipeline.min_hybrids

    run_logger.node_start("recombiner", n_input=len(selected), min_hybrids=min_hybrids)

    model_slug, temperature = get_agent_config(config, "recombiner")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_template = _load_prompt("recombiner_system.md")
    user_template = _load_prompt("recombiner_user.md")

    system_prompt = system_template.format(domain=domain, min_hybrids=min_hybrids)
    user_prompt = user_template.format(
        n_ideas=len(selected),
        domain=domain,
        min_hybrids=min_hybrids,
        ideas_json=_ideas_to_json(selected),
    )

    run_logger.info(f"Recombiner: generating hybrids from {len(selected)} ideas")

    hybrids = call_llm_structured_list(
        client=client,
        model=model_slug,
        temperature=temperature,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        item_schema=IdeaCandidate,
        repair_model=repair_slug,
        repair_temperature=repair_temp,
    )

    run_logger.llm_call("recombiner", model_slug, len(user_prompt), len(str(hybrids)))

    # Retry once if fewer than min_hybrids
    if len(hybrids) < min_hybrids:
        run_logger.warn(
            f"Recombiner: got {len(hybrids)} hybrids (< {min_hybrids}), retrying"
        )
        retry_user = user_template.format(
            n_ideas=len(selected),
            domain=domain,
            min_hybrids=min_hybrids,
            ideas_json=_ideas_to_json(selected),
        ) + "\n\nIMPORTANT: Combine pairs and triples of the input ideas. Produce at least {min_hybrids} hybrids.".format(min_hybrids=min_hybrids)

        retry_hybrids = call_llm_structured_list(
            client=client,
            model=model_slug,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=retry_user,
            item_schema=IdeaCandidate,
            repair_model=repair_slug,
            repair_temperature=repair_temp,
        )
        hybrids = retry_hybrids if len(retry_hybrids) >= len(hybrids) else hybrids

    # Fix IDs, source, domain
    for i, hybrid in enumerate(hybrids, 1):
        hybrid.id = f"hybrid_{i:03d}"
        hybrid.source = "hybrid"
        hybrid.domain = domain

    run_logger.info(f"Recombiner: produced {len(hybrids)} hybrids")
    run_logger.node_end("recombiner", n_hybrids=len(hybrids))

    state["hybrids"] = hybrids
    state["all_candidates"] = state["selected_ideas"] + hybrids
    return state
