"""paper_fetcher.py -- Fetch learning-science papers from Semantic Scholar.

Runs BEFORE the ideator. Searches for papers on biology/STEM learning
and stores them in state["evidence_papers"] for prompt injection.
"""
import asyncio
import logging
from typing import Any

import httpx

from src.logging_utils import RunLogger
from src.schemas import EvidencePaper, PipelineState

logger = logging.getLogger("idea_gen")

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,citationCount,fieldsOfStudy"

# Fixed queries covering core learning-science areas for biology/STEM
DEFAULT_QUERIES = [
    "spaced repetition biology learning retention",
    "active recall retrieval practice science education",
    "interleaving practice STEM exam performance",
    "formative assessment biology olympiad student achievement",
]


async def _fetch_query(
    client: httpx.AsyncClient, query: str, limit: int, timeout: int
) -> list[dict[str, Any]]:
    """Fetch one Semantic Scholar query. Returns raw result dicts."""
    try:
        resp = await client.get(
            SEMANTIC_SCHOLAR_URL,
            params={"query": query, "limit": limit, "fields": FIELDS},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        logger.warning(f"[WARN] paper_fetcher: query '{query}' failed: {exc}")
        return []


def _parse_paper(raw: dict[str, Any]) -> EvidencePaper | None:
    title = raw.get("title", "").strip()
    abstract = (raw.get("abstract") or "").strip()
    if not title or not abstract:
        return None
    return EvidencePaper(
        title=title,
        abstract=abstract[:400],  # truncate to 400 chars for prompt budget
        year=raw.get("year"),
        citation_count=raw.get("citationCount"),
        fields=[f.get("category", "") for f in (raw.get("fieldsOfStudy") or [])],
    )


def run_paper_fetcher(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Fetch learning-science papers and store in state["evidence_papers"]."""
    search_cfg = state["config"].search

    if not search_cfg.enabled:
        logger.info("[INFO] paper_fetcher: search disabled, skipping")
        state["evidence_papers"] = []
        return state

    run_logger.node_start("paper_fetcher")

    queries = DEFAULT_QUERIES[: search_cfg.n_queries]
    limit = search_cfg.max_results_per_query
    timeout = search_cfg.timeout_seconds

    async def _fetch_all() -> list[EvidencePaper]:
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[_fetch_query(client, q, limit, timeout) for q in queries]
            )
        papers = []
        seen_titles: set[str] = set()
        for batch in results:
            for raw in batch:
                paper = _parse_paper(raw)
                if paper and paper.title not in seen_titles:
                    seen_titles.add(paper.title)
                    papers.append(paper)
        # Sort by citation count (most cited = most established evidence)
        papers.sort(key=lambda p: p.citation_count or 0, reverse=True)
        return papers[:12]  # cap at 12 papers total for prompt budget

    papers = asyncio.run(_fetch_all())

    run_logger.info(f"[INFO] paper_fetcher: fetched {len(papers)} papers")
    run_logger.node_end("paper_fetcher", n_papers=len(papers))

    state["evidence_papers"] = papers
    return state
