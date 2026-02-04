import logging
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from src.schemas import PipelineState, IdeaCandidate, GateResult, AngelRescueResult
from src.config import get_agent_config, resolve_model
from src.llm import create_client, call_llm_structured
from src.scoring import apply_gate_thresholds
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


class GateLLMResponse(BaseModel):
    """Intermediate schema for parsing LLM output (no status/kill_reason)."""
    model_config = ConfigDict(strict=False)

    idea_id: str
    q1_wrapper_risk_score: int
    q1_reason: str
    q2_embedding_score: int
    q2_workflow_embedding: str
    q3_compounding_score: int
    q3_hard_to_copy_reason: str


def _attempt_angel_rescue(
    client,
    config,
    idea: IdeaCandidate,
    llm_scores: GateLLMResponse,
    kill_reason: str,
    run_logger: RunLogger,
) -> tuple[IdeaCandidate | None, AngelRescueResult | None]:
    """Angel's Rescue sub-routine: attempt to save a killed idea.

    Returns (rewritten_idea, rescue_result) if saved, or (None, rescue_result)
    if the angel confirms the kill.
    """
    rescue_model, rescue_temp = get_agent_config(config, "angel_rescue")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature

    system_prompt = _load_prompt("angel_rescue_system.md")
    user_template = _load_prompt("angel_rescue_user.md")

    thresholds = config.gatekeeper
    user_prompt = user_template.format(
        idea_name=idea.name,
        hook_loop=idea.hook_loop,
        ai_magic_moment=idea.ai_magic_moment,
        user_segment=idea.user_segment,
        mvp_scope=idea.mvp_scope,
        ai_essential_claim=idea.ai_essential_claim,
        compounding_advantage=idea.compounding_advantage or "Not specified",
        q1_score=llm_scores.q1_wrapper_risk_score,
        q2_score=llm_scores.q2_embedding_score,
        q3_score=llm_scores.q3_compounding_score,
        q1_threshold=thresholds.q1_kill_threshold,
        q2_threshold=thresholds.q2_kill_threshold,
        q3_threshold=thresholds.q3_kill_threshold,
        kill_reasons=kill_reason,
    )

    run_logger.info(f"Angel's Rescue: attempting to save '{idea.name}' ({idea.id})")

    rescue_result = call_llm_structured(
        client=client,
        model=rescue_model,
        temperature=rescue_temp,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=AngelRescueResult,
        repair_model=repair_slug,
        repair_temperature=repair_temp,
    )

    run_logger.llm_call("angel_rescue", rescue_model, len(user_prompt), 0)

    if rescue_result is None:
        run_logger.schema_fail("angel_rescue", idea.id, "Failed to parse rescue response")
        return None, None

    if rescue_result.verdict == "kill":
        run_logger.info(f"Angel's Rescue: confirmed kill for '{idea.name}'")
        return None, rescue_result

    # Rewrite idea with rescued fields
    rewritten = IdeaCandidate(
        id=idea.id,
        name=rescue_result.rewritten_name or idea.name,
        hook_loop=rescue_result.rewritten_hook_loop or idea.hook_loop,
        ai_magic_moment=rescue_result.rewritten_ai_magic_moment or idea.ai_magic_moment,
        user_segment=idea.user_segment,
        mvp_scope=rescue_result.rewritten_mvp_scope or idea.mvp_scope,
        ai_essential_claim=rescue_result.rewritten_ai_essential_claim or idea.ai_essential_claim,
        domain=idea.domain,
        source=idea.source,
        compounding_advantage=rescue_result.rewritten_compounding_advantage or idea.compounding_advantage,
    )

    run_logger.info(f"Angel's Rescue: saved '{idea.name}' -> '{rewritten.name}' (pivot: {rescue_result.pivot_feature})")
    return rewritten, rescue_result


def run_gatekeeper(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Node C: Anti-wrapper gatekeeper. 1 LLM call per candidate, programmatic thresholds.

    Includes Angel's Rescue sub-routine for killed ideas and starred-idea bypass.
    """
    config = state["config"]
    candidates = state["all_candidates"]
    starred_ids = set(state.get("starred_ids", []))

    run_logger.node_start("gatekeeper", n_candidates=len(candidates), n_starred=len(starred_ids))

    model_slug, temperature = get_agent_config(config, "gatekeeper")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    system_prompt = _load_prompt("gatekeeper_system.md")
    user_template = _load_prompt("gatekeeper_user.md")

    thresholds = config.gatekeeper
    gate_results: list[GateResult] = []
    survivors: list[IdeaCandidate] = []
    pass_count = 0
    kill_count = 0
    rescue_count = 0

    for idea in candidates:
        user_prompt = user_template.format(
            idea_name=idea.name,
            hook_loop=idea.hook_loop,
            ai_magic_moment=idea.ai_magic_moment,
            user_segment=idea.user_segment,
            mvp_scope=idea.mvp_scope,
            ai_essential_claim=idea.ai_essential_claim,
            compounding_advantage=idea.compounding_advantage or "Not specified",
        )

        llm_result = call_llm_structured(
            client=client,
            model=model_slug,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=GateLLMResponse,
            repair_model=repair_slug,
            repair_temperature=repair_temp,
        )

        run_logger.llm_call("gatekeeper", model_slug, len(user_prompt), 0)

        if llm_result is None:
            run_logger.schema_fail("gatekeeper", idea.id, "Failed to parse gatekeeper response")
            continue

        # Apply programmatic thresholds
        status, kill_reason = apply_gate_thresholds(
            wrapper_risk_score=llm_result.q1_wrapper_risk_score,
            embedding_score=llm_result.q2_embedding_score,
            compounding_score=llm_result.q3_compounding_score,
            q1_threshold=thresholds.q1_kill_threshold,
            q2_threshold=thresholds.q2_kill_threshold,
            q3_threshold=thresholds.q3_kill_threshold,
        )

        # Starred ideas: score for data but force PASS (no rescue needed)
        is_starred = idea.id in starred_ids
        rescued = False
        rescue_pivot = None

        if status == "KILL" and is_starred:
            run_logger.info(f"Gatekeeper: '{idea.name}' is starred -- forcing PASS")
            status = "PASS"
            kill_reason = None

        elif status == "KILL" and not is_starred:
            # Angel's Rescue: attempt to save before confirming kill
            rewritten_idea, rescue_result = _attempt_angel_rescue(
                client, config, idea, llm_result, kill_reason or "", run_logger,
            )

            if rewritten_idea is not None and rescue_result is not None:
                # Re-score the rewritten idea through gatekeeper
                rewrite_prompt = user_template.format(
                    idea_name=rewritten_idea.name,
                    hook_loop=rewritten_idea.hook_loop,
                    ai_magic_moment=rewritten_idea.ai_magic_moment,
                    user_segment=rewritten_idea.user_segment,
                    mvp_scope=rewritten_idea.mvp_scope,
                    ai_essential_claim=rewritten_idea.ai_essential_claim,
                    compounding_advantage=rewritten_idea.compounding_advantage or "Not specified",
                )

                rescore_result = call_llm_structured(
                    client=client,
                    model=model_slug,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    user_prompt=rewrite_prompt,
                    schema=GateLLMResponse,
                    repair_model=repair_slug,
                    repair_temperature=repair_temp,
                )
                run_logger.llm_call("gatekeeper", model_slug, len(rewrite_prompt), 0)

                if rescore_result is not None:
                    new_status, new_kill = apply_gate_thresholds(
                        wrapper_risk_score=rescore_result.q1_wrapper_risk_score,
                        embedding_score=rescore_result.q2_embedding_score,
                        compounding_score=rescore_result.q3_compounding_score,
                        q1_threshold=thresholds.q1_kill_threshold,
                        q2_threshold=thresholds.q2_kill_threshold,
                        q3_threshold=thresholds.q3_kill_threshold,
                    )

                    if new_status == "PASS":
                        # Rescue succeeded: use rewritten idea and new scores
                        idea = rewritten_idea
                        llm_result = rescore_result
                        status = "PASS"
                        kill_reason = None
                        rescued = True
                        rescue_pivot = rescue_result.pivot_feature
                        rescue_count += 1
                        run_logger.info(f"Angel's Rescue: re-scored PASS for '{idea.name}'")
                    else:
                        run_logger.info(f"Angel's Rescue: re-scored still KILL for '{idea.name}'")
                else:
                    run_logger.info(f"Angel's Rescue: re-score failed for '{idea.name}', confirming kill")

        gate_result = GateResult(
            idea_id=idea.id,
            q1_wrapper_risk_score=llm_result.q1_wrapper_risk_score,
            q1_reason=llm_result.q1_reason,
            q2_embedding_score=llm_result.q2_embedding_score,
            q2_workflow_embedding=llm_result.q2_workflow_embedding,
            q3_compounding_score=llm_result.q3_compounding_score,
            q3_hard_to_copy_reason=llm_result.q3_hard_to_copy_reason,
            status=status,
            kill_reason=kill_reason,
            rescued=rescued,
            rescue_pivot=rescue_pivot,
            starred=is_starred,
        )
        gate_results.append(gate_result)

        if status == "PASS":
            survivors.append(idea)
            pass_count += 1
            run_logger.gate_pass(idea.id)
        else:
            kill_count += 1
            run_logger.gate_kill(idea.id, kill_reason or "threshold triggered")

    run_logger.info(
        f"Gatekeeper: {pass_count} PASS, {kill_count} KILL, "
        f"{rescue_count} rescued out of {len(candidates)}"
    )
    run_logger.node_end("gatekeeper", pass_count=pass_count, kill_count=kill_count, rescued=rescue_count)

    state["gate_results"] = gate_results
    state["survivors"] = survivors
    return state
