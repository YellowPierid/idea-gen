"""
Node A.5b: Interactive user review of selected ideas.

Displays selected ideas and lets the user VETO or STAR them before
expensive downstream processing. Skipped when --no-pause is passed.
"""

from __future__ import annotations

import logging

import click

from src.schemas import PipelineState
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")


def run_user_review(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Interactive review: user can veto or star selected ideas.

    In non-interactive mode (state["interactive"] == False), this is a
    passthrough that leaves selected_ideas unchanged.
    """
    ideas = state["selected_ideas"]
    interactive = state.get("interactive", False)

    run_logger.node_start("user_review", n_ideas=len(ideas), interactive=interactive)

    if not interactive:
        run_logger.info("User review: skipped (non-interactive mode)")
        run_logger.node_end("user_review", skipped=True)
        return state

    # Display ideas for review
    click.echo()
    click.echo("=" * 60)
    click.echo("  IDEA REVIEW -- Inspect before downstream processing")
    click.echo("=" * 60)
    click.echo()

    for i, idea in enumerate(ideas, 1):
        click.echo(f"  [{i}] {idea.name}")
        click.echo(f"      Hook: {idea.hook_loop[:100]}...")
        click.echo(f"      AI Magic: {idea.ai_magic_moment[:100]}...")
        click.echo(f"      Segment: {idea.user_segment}")
        click.echo()

    click.echo("Actions:")
    click.echo("  VETO <numbers>  -- Remove ideas (e.g. 'VETO 3 5 7')")
    click.echo("  STAR <numbers>  -- Force-include ideas through gatekeeper (e.g. 'STAR 1 2')")
    click.echo("  Press Enter     -- Accept current selection unchanged")
    click.echo()

    vetoed_indices: set[int] = set()
    starred_indices: set[int] = set()

    while True:
        user_input = click.prompt("Review action", default="", show_default=False).strip()

        if not user_input:
            break

        parts = user_input.split()
        action = parts[0].upper()

        if action not in ("VETO", "STAR"):
            click.echo("  Unknown action. Use VETO, STAR, or press Enter.")
            continue

        try:
            numbers = [int(x) for x in parts[1:]]
        except ValueError:
            click.echo("  Invalid numbers. Example: 'VETO 3 5'")
            continue

        invalid = [n for n in numbers if n < 1 or n > len(ideas)]
        if invalid:
            click.echo(f"  Out of range: {invalid}. Valid range: 1-{len(ideas)}")
            continue

        if action == "VETO":
            vetoed_indices.update(n - 1 for n in numbers)
            click.echo(f"  Vetoed: {numbers}")
        elif action == "STAR":
            starred_indices.update(n - 1 for n in numbers)
            click.echo(f"  Starred: {numbers}")

    # Apply vetoes and stars
    filtered = []
    starred_ids: list[str] = list(state.get("starred_ids", []))

    for i, idea in enumerate(ideas):
        if i in vetoed_indices:
            run_logger.info(f"User review: vetoed '{idea.name}' ({idea.id})")
            continue
        if i in starred_indices:
            starred_ids.append(idea.id)
            run_logger.info(f"User review: starred '{idea.name}' ({idea.id})")
        filtered.append(idea)

    n_vetoed = len(vetoed_indices)
    n_starred = len(starred_indices)
    click.echo(f"\n  Result: {len(filtered)} ideas kept, {n_vetoed} vetoed, {n_starred} starred")

    run_logger.node_end("user_review", kept=len(filtered), vetoed=n_vetoed, starred=n_starred)

    state["selected_ideas"] = filtered
    state["starred_ids"] = starred_ids
    return state
