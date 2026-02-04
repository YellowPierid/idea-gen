"""
Configuration loading for the AI Idea Generator pipeline.

Reads config.yaml, resolves the API key from the environment, and returns
a fully typed PipelineConfig ready for downstream use.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from typing import Tuple

import yaml

from src.schemas import (
    AgentConfig, EmbeddingConfig, GatekeeperConfig, MemoryConfig,
    PipelineConfig, PipelineParams, SearchConfig, UserProfile,
)


def load_config(config_path: str = "config.yaml") -> PipelineConfig:
    """Load config.yaml and return a typed PipelineConfig.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file.  Defaults to ``config.yaml``
        in the current working directory.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    EnvironmentError
        If the required API-key environment variable is not set.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path.resolve()}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    # -- API key from environment -----------------------------------------------
    api_key_env = raw["openrouter"]["api_key_env"]
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise EnvironmentError(
            f"Environment variable '{api_key_env}' is not set. "
            "Please export your OpenRouter API key before running the pipeline."
        )

    # -- Build typed sub-configs ------------------------------------------------
    agents = {
        name: AgentConfig(**agent_def)
        for name, agent_def in raw["agents"].items()
    }

    embedding = EmbeddingConfig(**raw["embedding"])
    gatekeeper = GatekeeperConfig(**raw["gatekeeper"])
    pipeline_params = PipelineParams(**raw["pipeline"])

    # -- Optional: user profile ------------------------------------------------
    user_profile = None
    if "user_profile" in raw and raw["user_profile"]:
        user_profile = UserProfile(**raw["user_profile"])

    # -- Optional: search config -----------------------------------------------
    search = SearchConfig()
    if "search" in raw and raw["search"]:
        search = SearchConfig(**raw["search"])

    # -- Optional: memory config -----------------------------------------------
    memory = MemoryConfig()
    if "memory" in raw and raw["memory"]:
        memory = MemoryConfig(**raw["memory"])

    return PipelineConfig(
        base_url=raw["openrouter"]["base_url"],
        api_key=api_key,
        models=raw["models"],
        agents=agents,
        embedding=embedding,
        gatekeeper=gatekeeper,
        pipeline=pipeline_params,
        output_dir=raw["output"]["dir"],
        user_profile=user_profile,
        search=search,
        memory=memory,
    )


def resolve_model(config: PipelineConfig, friendly_name: str) -> str:
    """Map a friendly model name to its full OpenRouter slug.

    Parameters
    ----------
    config : PipelineConfig
        The loaded pipeline configuration.
    friendly_name : str
        Short alias such as ``"qwen-72b"``.

    Raises
    ------
    KeyError
        If the friendly name is not present in the models mapping.
    """
    try:
        return config.models[friendly_name]
    except KeyError:
        available = ", ".join(sorted(config.models.keys()))
        raise KeyError(
            f"Unknown model '{friendly_name}'. Available: {available}"
        )


def get_agent_config(config: PipelineConfig, agent_name: str) -> Tuple[str, float]:
    """Return (resolved_model_slug, temperature) for a named agent.

    Parameters
    ----------
    config : PipelineConfig
        The loaded pipeline configuration.
    agent_name : str
        Agent identifier (e.g. ``"ideator"``, ``"gatekeeper"``).

    Raises
    ------
    KeyError
        If the agent name is not defined in config.
    """
    try:
        agent = config.agents[agent_name]
    except KeyError:
        available = ", ".join(sorted(config.agents.keys()))
        raise KeyError(
            f"Unknown agent '{agent_name}'. Available: {available}"
        )

    slug = resolve_model(config, agent.model)
    return slug, agent.temperature
