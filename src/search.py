"""
DuckDuckGo market evidence search for the pre-ranker monetization scoring.

Provides graceful fallback: if the search fails or times out, returns None
and the pre-ranker falls back to LLM-only scoring.
"""

from __future__ import annotations

import logging

from src.schemas import SearchConfig

logger = logging.getLogger("idea_gen")


def search_market_evidence(
    idea_name: str,
    user_segment: str,
    search_config: SearchConfig,
) -> str | None:
    """Query DuckDuckGo for competitor/demand signals.

    Returns a short summary string of search results, or None on failure.
    """
    if not search_config.enabled:
        return None

    query = f"{idea_name} {user_segment} app competitor"

    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(
                ddgs.text(
                    query,
                    max_results=search_config.max_results,
                )
            )

        if not results:
            logger.info("Market search: no results for '%s'", query)
            return None

        summaries = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            summaries.append(f"- {title}: {body[:150]}")

        evidence = f"Market search results for '{query}':\n" + "\n".join(summaries)
        logger.info("Market search: found %d results for '%s'", len(results), query)
        return evidence

    except ImportError:
        logger.warning(
            "ddgs not installed. "
            "Install with: pip install ddgs>=6.0.0"
        )
        return None
    except Exception as e:
        logger.warning("Market search failed (graceful fallback): %s", e)
        return None
