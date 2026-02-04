"""
Shared utility for formatting user context from the optional UserProfile.

Used by ideator and pre_ranker to inject developer profile information
into prompts when configured.
"""

from __future__ import annotations

from src.schemas import PipelineConfig


def format_user_context(config: PipelineConfig) -> str:
    """Build a user-context string from the optional UserProfile.

    Returns an empty string if no profile is configured, so callers can
    safely inject it into prompt templates without conditional logic.
    """
    profile = config.user_profile
    if profile is None:
        return ""

    parts = []
    if profile.skills:
        parts.append(f"Developer skills: {', '.join(profile.skills)}")
    if profile.stack:
        parts.append(f"Preferred tech stack: {', '.join(profile.stack)}")
    if profile.past_projects:
        parts.append(f"Past projects: {', '.join(profile.past_projects)}")

    if not parts:
        return ""

    header = (
        "\n\nDeveloper Profile (prioritize ideas that leverage these unfair advantages):\n"
    )
    return header + "\n".join(f"- {p}" for p in parts)
