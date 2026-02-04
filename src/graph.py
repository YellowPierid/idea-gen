"""
LangGraph pipeline definition.

Wires all agent nodes into a sequential graph with conditional retry logic
after the gatekeeper node if all candidates are killed.
"""

import logging

from langgraph.graph import StateGraph, END

from src.schemas import PipelineState
from src.config import resolve_model
from src.llm import create_client, call_llm
from src.storage import OutputStore, load_global_history
from src.logging_utils import RunLogger
from src.agents.ideator import run_ideator, PAST_THEMES_PATH
from src.agents.selector import run_selector
from src.agents.recombiner import run_recombiner
from src.agents.gatekeeper import run_gatekeeper
from src.agents.principles_judge import run_principles_judge
from src.agents.pre_ranker import run_pre_ranker
from src.agents.dsr_designer import run_dsr_designer
from src.agents.ranker import run_ranker
from src.agents.user_review import run_user_review

logger = logging.getLogger("idea_gen")


def _wrap_node(node_fn, node_name, store, run_logger):
    """Wrap an agent node to add checkpointing after execution."""

    def wrapped(state: PipelineState) -> PipelineState:
        result = node_fn(state, run_logger)
        store.save_checkpoint(node_name, result)
        # Write intermediate outputs progressively
        _write_intermediate(store, node_name, result)
        run_logger.flush()
        return result

    wrapped.__name__ = node_name
    return wrapped


def _write_intermediate(store: OutputStore, node_name: str, state: PipelineState):
    """Write intermediate JSONL files after each node."""
    if node_name == "ideator" and state.get("raw_ideas"):
        store.write_jsonl("raw_ideas.jsonl", state["raw_ideas"])
    elif node_name == "selector" and state.get("selected_ideas"):
        store.write_jsonl("selected_ideas.jsonl", state["selected_ideas"])
    elif node_name == "recombiner" and state.get("hybrids"):
        store.write_jsonl("hybrids.jsonl", state["hybrids"])
    elif node_name == "gatekeeper" and state.get("gate_results"):
        store.write_jsonl("gate_results.jsonl", state["gate_results"])
    elif node_name == "principles_judge" and state.get("principle_scores"):
        store.write_jsonl("principle_scores.jsonl", state["principle_scores"])
    elif node_name == "pre_ranker" and state.get("pre_ranker_scores"):
        store.write_jsonl("pre_ranker_scores.jsonl", state["pre_ranker_scores"])
    elif node_name == "dsr_designer" and state.get("dsr_protocols"):
        _write_dsr_markdown(store, state)
    elif node_name == "ranker" and state.get("final_ranking"):
        _write_final_outputs(store, state)


def _write_dsr_markdown(store: OutputStore, state: PipelineState):
    """Generate dsr_protocols.md from DSRProtocol objects."""
    protocols = state.get("dsr_protocols", [])
    survivors = {idea.id: idea for idea in state.get("survivors", [])}
    lines = ["# DSR Validation Protocols\n"]
    for proto in protocols:
        idea = survivors.get(proto.idea_id)
        name = idea.name if idea else proto.idea_id
        lines.append(f"## {name}\n")
        lines.append(f"**Problem Framing:** {proto.problem_framing}\n")
        lines.append("**Assumptions:**")
        for a in proto.assumptions:
            lines.append(f"- {a}")
        lines.append("\n**Wizard-of-Oz Test Plan:**")
        for i, step in enumerate(proto.woz_test_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("\n**Hook Metrics:**")
        for k, v in proto.hook_metrics.items():
            lines.append(f"- {k}: {v}")
        lines.append("\n**$1 Reservation Test:**")
        rt = proto.reservation_test
        lines.append(f"- Offer: {rt.offer_description}")
        lines.append(f"- Target Persona: {rt.target_persona}")
        lines.append(f"- Headline: {rt.headline}")
        lines.append(f"- Value Prop: {rt.value_proposition}")
        lines.append("- Conversion Drivers: " + ", ".join(rt.conversion_drivers))
        lines.append("- Objections: " + ", ".join(rt.anticipated_objections))
        lines.append("\n**Trust Breakers:**")
        for tb in proto.trust_breakers:
            lines.append(f"- {tb}")
        lines.append(f"\n**Falsification Criteria:** {proto.falsification_criteria}")
        lines.append("\n---\n")
    store.write_markdown("dsr_protocols.md", "\n".join(lines))


def _write_final_outputs(store: OutputStore, state: PipelineState):
    """Generate final_ranked.md and next_7_days_plan.md."""
    rankings = state.get("final_ranking", [])
    survivors = {idea.id: idea for idea in state.get("survivors", [])}

    # final_ranked.md
    lines = ["# Final Ranked Ideas\n"]
    if len(rankings) < 5:
        lines.append(
            f"*Note: Only {len(rankings)} idea(s) survived the gatekeeper. "
            "See gate_results.jsonl for kill reasons.*\n"
        )
    for fr in rankings:
        lines.append(f"## #{fr.rank}: {fr.idea_name}")
        lines.append(f"**ID:** {fr.idea_id}")
        lines.append(f"**Total Score:** {fr.total_score:.3f}")
        lines.append(f"**Principles:** {fr.principle_score}/10 | "
                      f"**Feasibility:** {fr.feasibility_score}/2 | "
                      f"**Habit:** {fr.habit_score}/2 | "
                      f"**Monetization:** {fr.monetization_score}/2")
        idea = survivors.get(fr.idea_id)
        if idea:
            lines.append(f"\n*Hook Loop:* {idea.hook_loop}")
            lines.append(f"*AI Magic Moment:* {idea.ai_magic_moment}")
            lines.append(f"*MVP Scope:* {idea.mvp_scope}")
        lines.append(f"\n**Rationale:** {fr.rationale}")
        lines.append("\n---\n")
    store.write_markdown("final_ranked.md", "\n".join(lines))

    # next_7_days_plan.md
    plan = state.get("_seven_day_plan", "")
    if not plan and rankings:
        plan = _default_7_day_plan(rankings[0].idea_name)
    if plan:
        store.write_markdown("next_7_days_plan.md", f"# 7-Day Execution Plan\n\n{plan}\n")


def _default_7_day_plan(idea_name: str) -> str:
    """Fallback 7-day plan template if LLM doesn't provide one."""
    return (
        f"## {idea_name}\n\n"
        "### Day 1-2: Landing Page + Interview Script + WOZ Setup\n"
        "- Create a landing page describing the core value proposition\n"
        "- Draft a 5-question user interview script\n"
        "- Set up a Wizard-of-Oz prototype (manual backend)\n\n"
        "### Day 3-4: Recruit Testers + Run Tests\n"
        "- Recruit 5-10 target users from the user segment\n"
        "- Run WOZ tests and collect feedback\n"
        "- Track activation and engagement metrics\n\n"
        "### Day 5: Analyze Results + Decision\n"
        "- Compile test results and user feedback\n"
        "- Evaluate against falsification criteria\n"
        "- Make go/no-go decision\n\n"
        "### Day 6-7: Build MVP Thin Slice or Pivot\n"
        "- If go: build the smallest functional slice of the product\n"
        "- If no-go: document learnings and pivot to next-ranked idea\n"
    )


def _update_past_themes(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Post-pipeline maintenance: summarize global history into past themes.

    Reads all idea names from global history, asks the LLM to distill
    overused themes, and writes the summary to past_themes.md so the
    next run's ideator avoids them (Tier 2 soft memory).
    """
    config = state["config"]
    history_dir = config.memory.history_dir
    records, _ = load_global_history(history_dir)

    if len(records) < 10:
        run_logger.info(
            "Themes update: only %d ideas in history, skipping summary",
            len(records),
        )
        return state

    run_logger.info("Themes update: summarizing %d past ideas", len(records))

    # Build a compact list of idea names for the LLM
    idea_names = [r.get("name", "unnamed") for r in records]
    idea_list = "\n".join(f"- {name}" for name in idea_names)

    model_slug = resolve_model(config, config.agents["ideator"].model)
    client = create_client(config.base_url, config.api_key)

    system_prompt = (
        "You are a research assistant. Given a list of past AI app ideas, "
        "identify the most over-represented themes. Return ONLY a bulleted "
        "list of 5-15 theme descriptions (one per line, starting with '- '). "
        "Each theme should be a short phrase (3-8 words). No preamble, no "
        "numbering, no explanation."
    )
    user_prompt = (
        f"Here are {len(idea_names)} past AI app ideas:\n\n"
        f"{idea_list}\n\n"
        "Summarize the most over-represented themes as a bulleted list."
    )

    try:
        summary = call_llm(
            client=client,
            model=model_slug,
            temperature=0.3,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        summary = summary.strip()
        if summary:
            PAST_THEMES_PATH.parent.mkdir(parents=True, exist_ok=True)
            PAST_THEMES_PATH.write_text(summary, encoding="utf-8")
            run_logger.info("Themes update: wrote past_themes.md")
    except Exception as e:
        run_logger.warning("Themes update failed (non-fatal): %s", e)

    return state


def _should_retry(state: PipelineState) -> str:
    """Conditional edge after gatekeeper: retry ideator or continue."""
    survivors = state.get("survivors", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state["config"].pipeline.max_retries

    if len(survivors) == 0 and retry_count < max_retries:
        logger.info("All candidates killed. Retrying ideator with new segments.")
        return "retry"
    return "continue"


def _prepare_retry(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Reset state for ideator retry with incremented retry count."""
    run_logger.info("Preparing retry with different user segments")
    state["retry_count"] = state.get("retry_count", 0) + 1
    state["raw_ideas"] = []
    state["selected_ideas"] = []
    state["hybrids"] = []
    state["all_candidates"] = []
    state["gate_results"] = []
    state["survivors"] = []
    return state


def build_graph(store: OutputStore, run_logger: RunLogger) -> StateGraph:
    """Build the LangGraph pipeline."""

    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("ideator", _wrap_node(run_ideator, "ideator", store, run_logger))
    graph.add_node("selector", _wrap_node(run_selector, "selector", store, run_logger))
    graph.add_node("user_review", _wrap_node(run_user_review, "user_review", store, run_logger))
    graph.add_node("recombiner", _wrap_node(run_recombiner, "recombiner", store, run_logger))
    graph.add_node("gatekeeper", _wrap_node(run_gatekeeper, "gatekeeper", store, run_logger))
    graph.add_node("retry_prep", lambda state: _prepare_retry(state, run_logger))
    graph.add_node("principles_judge", _wrap_node(run_principles_judge, "principles_judge", store, run_logger))
    graph.add_node("pre_ranker", _wrap_node(run_pre_ranker, "pre_ranker", store, run_logger))
    graph.add_node("dsr_designer", _wrap_node(run_dsr_designer, "dsr_designer", store, run_logger))
    graph.add_node("ranker", _wrap_node(run_ranker, "ranker", store, run_logger))
    graph.add_node(
        "update_themes",
        lambda state: _update_past_themes(state, run_logger),
    )

    # Linear flow with conditional retry after gatekeeper
    graph.set_entry_point("ideator")
    graph.add_edge("ideator", "selector")
    graph.add_edge("selector", "user_review")
    graph.add_edge("user_review", "recombiner")
    graph.add_edge("recombiner", "gatekeeper")

    graph.add_conditional_edges(
        "gatekeeper",
        _should_retry,
        {
            "retry": "retry_prep",
            "continue": "principles_judge",
        },
    )
    graph.add_edge("retry_prep", "ideator")

    graph.add_edge("principles_judge", "pre_ranker")
    graph.add_edge("pre_ranker", "dsr_designer")
    graph.add_edge("dsr_designer", "ranker")
    graph.add_edge("ranker", "update_themes")
    graph.add_edge("update_themes", END)

    return graph
