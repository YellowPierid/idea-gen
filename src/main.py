"""
CLI entry point for the AI Idea Generator pipeline.

Commands:
    run          Run the full pipeline
    inspect      Inspect a past run's outputs
    config-check Validate config and test connectivity
"""

import logging
import random
import sys
from pathlib import Path

import click
import numpy as np

from src.config import load_config, get_agent_config
from src.graph import build_graph
from src.llm import create_client, call_llm
from src.logging_utils import RunLogger
from src.schemas import PipelineState
from src.storage import OutputStore


def _setup_logging(level: str = "INFO"):
    """Configure root logger for console output."""
    root = logging.getLogger("idea_gen")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


@click.group()
def cli():
    """AI-Native Productivity App Idea Generator."""
    pass


@cli.command()
@click.option("--n_raw", type=int, default=None, help="Number of raw ideas to generate")
@click.option("--top_k", type=int, default=None, help="Number of ideas to select")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility")
@click.option("--domain", type=str, default=None, help="Target domain")
@click.option("--resume", type=str, default=None, help="Resume a previous run by run_id")
@click.option("--no-pause", is_flag=True, default=False, help="Skip interactive review pause")
@click.option("--config-path", type=str, default="config.yaml", help="Path to config file")
def run(n_raw, top_k, seed, domain, resume, no_pause, config_path):
    """Run the full idea generation pipeline."""
    _setup_logging()
    logger = logging.getLogger("idea_gen")

    try:
        config = load_config(config_path)
    except (FileNotFoundError, EnvironmentError) as e:
        logger.error(str(e))
        sys.exit(1)

    # Apply CLI overrides
    if n_raw is not None:
        config.pipeline.n_raw = n_raw
    if top_k is not None:
        config.pipeline.top_k = top_k
    if seed is not None:
        config.pipeline.seed = seed
    if domain is not None:
        config.pipeline.domain = domain

    # Seed local randomness
    random.seed(config.pipeline.seed)
    np.random.seed(config.pipeline.seed)

    # Setup storage
    store = OutputStore(config.output_dir, run_id=resume)
    run_logger = RunLogger(store.run_dir)

    logger.info("Pipeline run: %s", store.run_dir.name)
    logger.info("Domain: %s | n_raw: %d | top_k: %d | seed: %d",
                config.pipeline.domain, config.pipeline.n_raw,
                config.pipeline.top_k, config.pipeline.seed)

    # Check for resume
    initial_state: PipelineState = {
        "config": config,
        "raw_ideas": [],
        "selected_ideas": [],
        "hybrids": [],
        "all_candidates": [],
        "gate_results": [],
        "survivors": [],
        "principle_scores": [],
        "pre_ranker_scores": [],
        "dsr_protocols": [],
        "final_ranking": [],
        "retry_count": 0,
        "starred_ids": [],
        "interactive": not no_pause,
    }

    if resume:
        checkpoint = store.load_checkpoint()
        if checkpoint:
            logger.info("Resuming from node: %s", checkpoint["last_completed_node"])
            # Restore state from checkpoint (simplified -- full restore would
            # reconstruct Pydantic models from dicts, but for MVP we restart
            # from the last completed node's outputs)
            logger.info("Resume support: restarting pipeline (full state restore TBD)")

    # Build and run the graph
    graph = build_graph(store, run_logger)
    compiled = graph.compile()

    logger.info("--- Pipeline starting ---")
    try:
        final_state = compiled.invoke(initial_state)
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        run_logger.log_event("pipeline", "error", {"error": str(e)})
        run_logger.flush()
        raise

    # Final summary
    n_survivors = len(final_state.get("final_ranking", []))
    logger.info("--- Pipeline complete ---")
    logger.info("Final ranking: %d idea(s)", n_survivors)
    if n_survivors > 0:
        top = final_state["final_ranking"][0]
        logger.info("Top idea: #%d %s (score: %.3f)", top.rank, top.idea_name, top.total_score)
    logger.info("Outputs: %s", store.run_dir)

    run_logger.log_event("pipeline", "complete", {"n_ranked": n_survivors})
    run_logger.flush()


@cli.command()
@click.argument("run_id")
@click.option("--config-path", type=str, default="config.yaml", help="Path to config file")
def inspect(run_id, config_path):
    """Inspect a past run's outputs."""
    _setup_logging()
    logger = logging.getLogger("idea_gen")

    try:
        config = load_config(config_path)
    except (FileNotFoundError, EnvironmentError) as e:
        logger.error(str(e))
        sys.exit(1)

    store = OutputStore(config.output_dir, run_id=run_id)
    run_dir = store.run_dir

    click.echo(f"Run: {run_id}")
    click.echo(f"Directory: {run_dir}")
    click.echo()

    # List output files
    files = sorted(run_dir.iterdir())
    for f in files:
        size = f.stat().st_size
        click.echo(f"  {f.name:30s}  {size:>8,} bytes")

    # Show checkpoint status
    checkpoint = store.load_checkpoint()
    if checkpoint:
        click.echo()
        click.echo(f"Last completed node: {checkpoint['last_completed_node']}")
        click.echo(f"Timestamp: {checkpoint['timestamp']}")

    # Show final ranking if exists
    ranked_path = run_dir / "final_ranked.md"
    if ranked_path.exists():
        click.echo()
        click.echo("--- Final Ranking ---")
        click.echo(ranked_path.read_text(encoding="utf-8")[:2000])


@cli.command("config-check")
@click.option("--config-path", type=str, default="config.yaml", help="Path to config file")
def config_check(config_path):
    """Validate configuration and test OpenRouter connectivity."""
    _setup_logging()
    logger = logging.getLogger("idea_gen")

    # Step 1: Load config
    click.echo("[INFO] Loading configuration...")
    try:
        config = load_config(config_path)
        click.echo("[OK] Configuration loaded successfully")
    except FileNotFoundError as e:
        click.echo(f"[FAIL] {e}")
        sys.exit(1)
    except EnvironmentError as e:
        click.echo(f"[FAIL] {e}")
        sys.exit(1)

    # Step 2: Check model mappings
    click.echo("[INFO] Checking model mappings...")
    for agent_name in config.agents:
        slug, temp = get_agent_config(config, agent_name)
        click.echo(f"  {agent_name:20s} -> {slug} (temp={temp})")
    click.echo("[OK] All model mappings valid")

    # Step 3: Test API connectivity
    click.echo("[INFO] Testing OpenRouter API connectivity...")
    try:
        client = create_client(config.base_url, config.api_key)
        # Use the cheapest model for a simple test
        response = call_llm(
            client=client,
            model=config.models.get("qwen-14b", "qwen/qwen-2.5-14b-instruct"),
            temperature=0.0,
            system_prompt="You are a test assistant.",
            user_prompt="Reply with exactly: OK",
        )
        if response.strip():
            click.echo(f"[OK] API connection successful (response: {response.strip()[:50]})")
        else:
            click.echo("[WARN] API returned empty response")
    except Exception as e:
        click.echo(f"[FAIL] API connection failed: {e}")
        sys.exit(1)

    # Step 4: Check prompt files
    click.echo("[INFO] Checking prompt templates...")
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    expected_prompts = [
        "ideator_system.md", "ideator_user.md",
        "recombiner_system.md", "recombiner_user.md",
        "gatekeeper_system.md", "gatekeeper_user.md",
        "principles_judge_system.md", "principles_judge_user.md",
        "pre_ranker_system.md", "pre_ranker_user.md",
        "dsr_designer_system.md", "dsr_designer_user.md",
        "ranker_system.md", "ranker_user.md",
        "angel_rescue_system.md", "angel_rescue_user.md",
    ]
    missing = [p for p in expected_prompts if not (prompts_dir / p).exists()]
    if missing:
        click.echo(f"[WARN] Missing prompt files: {', '.join(missing)}")
    else:
        click.echo(f"[OK] All {len(expected_prompts)} prompt templates found")

    click.echo()
    click.echo("[OK] Configuration check complete. Ready to run pipeline.")


if __name__ == "__main__":
    cli()
