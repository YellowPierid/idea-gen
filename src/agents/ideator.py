import logging
from pathlib import Path

import numpy as np

from src.schemas import PipelineState, IdeaCandidate
from src.config import get_agent_config, resolve_model
from src.embeddings import get_embeddings
from src.llm import create_client, call_llm_structured_list
from src.logging_utils import RunLogger
from src.prompt_utils import format_user_context
from src.storage import load_global_history, save_global_history
from src.reme_memory import search_patterns as reme_search_patterns

logger = logging.getLogger("idea_gen")

# Default user segments for biology olympiad domain (3 calls)
DEFAULT_SEGMENTS = [
    "High-school students (ages 15-18) preparing for national biology olympiad selection rounds",
    "Undergraduate students (ages 18-22) competing in IBO or national university-level biology competitions",
    "Self-directed learners with no olympiad coach who need structured feedback on olympiad-depth material",
]

# Retry segments (used if all ideas killed by gatekeeper)
RETRY_SEGMENTS = [
    "Students who passed the first round and need to close specific knowledge gaps under time pressure",
    "Students who struggle with lab practical skills and experimental design questions",
    "Students transitioning from school biology to olympiad depth (enzyme kinetics, phylogenetics, Hardy-Weinberg)",
]

DOMAIN_DESCRIPTIONS = {
    "productivity": "planning, writing, decision-making, meeting workflows, project execution, personal organization, learning-for-work",
    "productivity_android": "offline-first Android apps for on-the-go capture, short-session productivity, and AI-enriched workflows that sync when connected",
    "personal_analytics_pc": "plain-English data assistants for non-technical users -- users bring their own data export, Claude reads and indexes it, users ask questions in natural language and get plain English answers; built as Python + Streamlit desktop apps",
    "health": "wellness tracking, health management, fitness planning, mental health support",
    "education": "learning platforms, skill development, tutoring, educational content",
    "finance": "personal finance, budgeting, investment, financial planning",
    "biology_olympiad": "evidence-grounded web apps for high-school and undergraduate students preparing for biology olympiad competitions (IBO, national olympiads, AP Biology); ideas must use known learning science mechanics and address olympiad-level material beyond standard school biology",
}

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PAST_THEMES_PATH = PROMPTS_DIR / "context" / "past_themes.md"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _format_evidence_context(papers: list) -> str:
    """Format fetched papers as a prompt-injectable evidence context block."""
    if not papers:
        return ""
    lines = ["## Validated Learning Science (cite these in your ideas)\n"]
    for i, p in enumerate(papers[:8], 1):  # max 8 papers in prompt
        year_str = f" ({p.year})" if p.year else ""
        lines.append(f"{i}. **{p.title}**{year_str}")
        lines.append(f"   {p.abstract}\n")
    return "\n".join(lines)


_OLYMPIAD_PERSONA = """\
## Active Persona: Former Olympiad Student / Study Methods Researcher
Generate ideas through the lens of someone who:
- Trained for biology olympiad themselves and knows the specific knowledge gaps
- Is obsessed with evidence-based study techniques (not just "study harder")
- Understands that olympiad prep differs from school exams in depth and question style
- Wants tools that reduce rote memorization and increase mechanistic understanding
Generate ideas this person would build for their past self.\
"""


def _maybe_inject_persona(system_prompt: str, rotate: bool) -> str:
    if not rotate:
        return system_prompt
    return _OLYMPIAD_PERSONA + "\n\n" + system_prompt


def _idea_to_text(idea: IdeaCandidate) -> str:
    """Concatenate key fields for embedding (matches selector pattern)."""
    return f"{idea.name} {idea.hook_loop} {idea.ai_magic_moment}"


def _load_past_themes() -> str:
    """Load past themes restriction text, or empty string if none yet."""
    if PAST_THEMES_PATH.exists():
        content = PAST_THEMES_PATH.read_text(encoding="utf-8").strip()
        if content:
            return (
                "\nRESTRICTION: We have already fully explored the following "
                "themes. DO NOT generate ideas related to:\n"
                f"{content}\n"
                "Focus on unexplored niches.\n"
            )
    return ""


def _load_reme_patterns(config) -> str:
    """Tier 3 (procedural memory): retrieve past winning patterns from ReMeLight.

    Returns a formatted prompt suffix, or empty string if no memories yet or on error.
    """
    reme_cfg = getattr(config, "reme_light", None)
    if not reme_cfg:
        return ""
    working_dir = getattr(reme_cfg, "working_dir", None)
    model = getattr(reme_cfg, "model", "")
    if not working_dir:
        return ""
    patterns = reme_search_patterns(
        query="successful ideas that passed gatekeeper, high-scoring domains and idea patterns",
        working_dir=working_dir,
        model=model,
    )
    if not patterns:
        return ""
    return (
        "\n\nPAST WINNING PATTERNS (learned from previous pipeline runs):\n"
        f"{patterns}\n"
        "Use these patterns to guide idea generation toward approaches that have proven successful.\n"
    )


def _filter_duplicates(
    new_ideas: list[IdeaCandidate],
    history_records: list[dict],
    history_vectors: np.ndarray | None,
    threshold: float,
    client,
    embed_model: str,
    embed_fallback: str,
    run_logger: RunLogger,
) -> tuple[list[IdeaCandidate], list[dict], np.ndarray | None]:
    """Remove ideas that are semantically too similar to past ideas.

    Returns (unique_ideas, updated_records, updated_vectors).
    """
    if not new_ideas:
        return new_ideas, history_records, history_vectors

    # Embed the new ideas
    new_texts = [_idea_to_text(idea) for idea in new_ideas]
    new_vectors = get_embeddings(
        texts=new_texts,
        client=client,
        model=embed_model,
        fallback=embed_fallback,
    )

    unique_ideas = []
    unique_new_vectors = []

    for i, idea in enumerate(new_ideas):
        vec = new_vectors[i]
        is_duplicate = False

        if history_vectors is not None and history_vectors.shape[0] > 0:
            # Cosine similarity against all history vectors
            norms_hist = np.linalg.norm(history_vectors, axis=1, keepdims=True)
            norm_vec = np.linalg.norm(vec)
            if norm_vec > 0:
                # Avoid division by zero in history norms
                safe_norms = np.where(norms_hist > 0, norms_hist, 1.0)
                similarities = (history_vectors @ vec) / (safe_norms.squeeze() * norm_vec)
                if np.max(similarities) > threshold:
                    run_logger.info(
                        f"Ideator: duplicate filtered -- '{idea.name}' "
                        f"(max_sim={np.max(similarities):.3f})"
                    )
                    is_duplicate = True

        if not is_duplicate:
            unique_ideas.append(idea)
            unique_new_vectors.append(vec)
            # Also add to history in-memory so later ideas in this batch
            # are checked against earlier ones
            new_record = {"name": idea.name, "text": new_texts[i]}
            history_records.append(new_record)
            if history_vectors is not None:
                history_vectors = np.vstack([history_vectors, vec.reshape(1, -1)])
            else:
                history_vectors = vec.reshape(1, -1)

    run_logger.info(
        f"Ideator: novelty filter kept {len(unique_ideas)}/{len(new_ideas)} ideas"
    )
    return unique_ideas, history_records, history_vectors


def _generate_batch(
    client,
    model_slug: str,
    temperature: float,
    system_prompt: str,
    user_template: str,
    n_ideas: int,
    domain: str,
    segment: str,
    repair_slug: str,
    repair_temp: float,
    run_logger: RunLogger,
) -> list[IdeaCandidate]:
    """Run a single LLM call for one segment and return parsed ideas."""
    user_prompt = user_template.format(
        n_ideas=n_ideas,
        domain=domain,
        user_segment=segment,
    )

    run_logger.info(f"Ideator: generating {n_ideas} ideas for '{segment}'")

    ideas = call_llm_structured_list(
        client=client,
        model=model_slug,
        temperature=temperature,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        item_schema=IdeaCandidate,
        repair_model=repair_slug,
        repair_temperature=repair_temp,
    )

    run_logger.llm_call("ideator", model_slug, len(user_prompt), len(str(ideas)))
    return ideas


def run_ideator(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Node A: Generate diverse raw ideas via 3 LLM calls by user segment.

    Produces n_raw ideas total (n_raw/3 per call, 3 calls).
    After generation, applies the Tier 1 (hard) novelty filter to remove
    ideas that are semantically too similar to past runs. If the filter
    removes ideas, additional LLM calls backfill the deficit.
    """
    config = state["config"]
    n_raw = config.pipeline.n_raw
    domain = config.pipeline.domain
    n_per_call = n_raw // 3
    retry_count = state.get("retry_count", 0)

    # Pick segments based on retry count
    if retry_count == 0:
        segments = DEFAULT_SEGMENTS
    else:
        segments = RETRY_SEGMENTS

    run_logger.node_start("ideator", n_raw=n_raw, segments=segments)

    # Setup LLM client
    model_slug, temperature = get_agent_config(config, "ideator")
    repair_slug = resolve_model(config, config.agents["schema_repair"].model)
    repair_temp = config.agents["schema_repair"].temperature
    client = create_client(config.base_url, config.api_key)

    # Load prompt templates
    system_template = _load_prompt("ideator_system.md")
    user_template = _load_prompt("ideator_user.md")

    domain_desc = DOMAIN_DESCRIPTIONS.get(domain, domain)
    user_context = format_user_context(config)

    # Tier 2 (soft memory): inject past themes into system prompt
    past_themes = _load_past_themes()

    # Tier 3 (procedural memory): retrieve past winning patterns from ReMeLight
    reme_patterns = _load_reme_patterns(config)

    # Android profile context (appended to system prompt after format)
    android_profile = state.get("android_profile", "")

    # Load global history for Tier 1 (hard memory)
    history_dir = config.memory.history_dir
    threshold = config.memory.similarity_threshold
    history_records, history_vectors = load_global_history(history_dir)
    run_logger.info(
        f"Ideator: loaded {len(history_records)} ideas from global history"
    )

    all_ideas: list[IdeaCandidate] = []
    idea_counter = 1

    # Phase 1: generate from all segments
    for segment in segments:
        system_prompt = system_template.format(
            domain=domain,
            domain_description=domain_desc,
            user_context=user_context,
            past_themes=past_themes,
        )
        if android_profile:
            system_prompt += (
                f"\n\n## Target Platform Profile\n"
                f"Platform context for this run: {android_profile}\n"
                f"Generate ideas that are natural fits for this platform and deployment context."
            )
        # Tier 3: append ReMeLight patterns (empty string when no memories yet)
        system_prompt += reme_patterns
        # Inject evidence papers + persona rotation
        evidence_papers = state.get("evidence_papers", [])
        rotate_persona = state.get("rotate_persona", False)
        evidence_block = _format_evidence_context(evidence_papers)
        if evidence_block:
            system_prompt = system_prompt + "\n\n" + evidence_block
        system_prompt = _maybe_inject_persona(system_prompt, rotate_persona)

        ideas = _generate_batch(
            client, model_slug, temperature, system_prompt, user_template,
            n_per_call, domain, segment, repair_slug, repair_temp, run_logger,
        )

        # Assign sequential IDs
        for idea in ideas:
            idea.id = f"idea_{idea_counter:03d}"
            idea.domain = domain
            idea.source = "raw"
            idea_counter += 1

        # Tier 1 (hard memory): filter duplicates against global history
        unique, history_records, history_vectors = _filter_duplicates(
            new_ideas=ideas,
            history_records=history_records,
            history_vectors=history_vectors,
            threshold=threshold,
            client=client,
            embed_model=config.embedding.model,
            embed_fallback=config.embedding.fallback,
            run_logger=run_logger,
        )

        all_ideas.extend(unique)
        run_logger.info(f"Ideator: got {len(unique)} unique ideas for '{segment}'")

    state["rotate_persona"] = False  # reset after first use

    # Phase 2: backfill if novelty filter removed too many ideas
    deficit = n_raw - len(all_ideas)
    backfill_round = 0
    max_backfill_rounds = 2

    while deficit > 0 and backfill_round < max_backfill_rounds:
        backfill_round += 1
        # Cycle through segments for backfill
        segment = segments[backfill_round % len(segments)]
        run_logger.info(
            f"Ideator: backfilling {deficit} ideas (round {backfill_round})"
        )

        system_prompt = system_template.format(
            domain=domain,
            domain_description=domain_desc,
            user_context=user_context,
            past_themes=past_themes,
        )
        if android_profile:
            system_prompt += (
                f"\n\n## Target Platform Profile\n"
                f"Platform context for this run: {android_profile}\n"
                f"Generate ideas that are natural fits for this platform and deployment context."
            )
        # Tier 3: append ReMeLight patterns (empty string when no memories yet)
        system_prompt += reme_patterns
        # Inject evidence papers + persona rotation
        evidence_papers = state.get("evidence_papers", [])
        rotate_persona = state.get("rotate_persona", False)
        evidence_block = _format_evidence_context(evidence_papers)
        if evidence_block:
            system_prompt = system_prompt + "\n\n" + evidence_block
        system_prompt = _maybe_inject_persona(system_prompt, rotate_persona)

        ideas = _generate_batch(
            client, model_slug, temperature, system_prompt, user_template,
            deficit, domain, segment, repair_slug, repair_temp, run_logger,
        )

        for idea in ideas:
            idea.id = f"idea_{idea_counter:03d}"
            idea.domain = domain
            idea.source = "raw"
            idea_counter += 1

        unique, history_records, history_vectors = _filter_duplicates(
            new_ideas=ideas,
            history_records=history_records,
            history_vectors=history_vectors,
            threshold=threshold,
            client=client,
            embed_model=config.embedding.model,
            embed_fallback=config.embedding.fallback,
            run_logger=run_logger,
        )

        all_ideas.extend(unique)
        deficit = n_raw - len(all_ideas)

    # Persist updated global history
    if history_vectors is not None:
        save_global_history(history_dir, history_records, history_vectors)
        run_logger.info(
            f"Ideator: saved {len(history_records)} total ideas to global history"
        )

    run_logger.node_end("ideator", total_ideas=len(all_ideas))

    state["raw_ideas"] = all_ideas
    return state
