import logging
import numpy as np
from sklearn.cluster import KMeans
from src.schemas import PipelineState, IdeaCandidate
from src.embeddings import get_embeddings
from src.llm import create_client
from src.logging_utils import RunLogger

logger = logging.getLogger("idea_gen")


def _idea_to_text(idea: IdeaCandidate) -> str:
    """Concatenate key fields for embedding."""
    return f"{idea.name} {idea.hook_loop} {idea.ai_magic_moment} {idea.ai_essential_claim}"


def run_selector(state: PipelineState, run_logger: RunLogger) -> PipelineState:
    """Node A.5: Select top_k diverse ideas via embedding clustering."""
    config = state["config"]
    top_k = config.pipeline.top_k
    raw_ideas = state["raw_ideas"]
    seed = config.pipeline.seed

    run_logger.node_start("selector", n_input=len(raw_ideas), top_k=top_k)

    if len(raw_ideas) <= top_k:
        run_logger.info(f"Selector: {len(raw_ideas)} ideas <= top_k={top_k}, keeping all")
        state["selected_ideas"] = raw_ideas
        run_logger.node_end("selector", n_selected=len(raw_ideas))
        return state

    # Step 1: Compute embeddings
    texts = [_idea_to_text(idea) for idea in raw_ideas]
    client = create_client(config.base_url, config.api_key)

    embeddings = get_embeddings(
        texts=texts,
        client=client,
        model=config.embedding.model,
        fallback=config.embedding.fallback,
    )

    run_logger.info(f"Selector: computed embeddings, shape={embeddings.shape}")

    # Step 2: K-means clustering
    kmeans = KMeans(n_clusters=top_k, random_state=seed, n_init=10)
    kmeans.fit(embeddings)

    # Step 3: Pick idea closest to each centroid
    selected_indices = []
    for cluster_idx in range(top_k):
        # Find all ideas in this cluster
        cluster_mask = kmeans.labels_ == cluster_idx
        cluster_indices = np.where(cluster_mask)[0]

        if len(cluster_indices) == 0:
            continue

        # Find the one closest to centroid
        centroid = kmeans.cluster_centers_[cluster_idx]
        distances = np.linalg.norm(embeddings[cluster_indices] - centroid, axis=1)
        best_in_cluster = cluster_indices[np.argmin(distances)]
        selected_indices.append(best_in_cluster)

    selected = [raw_ideas[i] for i in selected_indices]

    run_logger.info(f"Selector: selected {len(selected)} diverse ideas from {len(raw_ideas)}")
    run_logger.node_end("selector", n_selected=len(selected))

    state["selected_ideas"] = selected
    return state
