"""paper_rag.py -- RAG node: embed local PDFs and retrieve relevant chunks.

Runs BEFORE the ideator (replaces paper_fetcher). Discovers PDFs in
data/papers/, chunks and embeds them, then retrieves the top-12 chunks most
similar to the pipeline's domain description and stores them in
state["evidence_papers"] for prompt injection.
"""
from pathlib import Path

import numpy as np
import pypdf

from src.embeddings import get_embeddings
from src.llm import create_client
from src.schemas import EvidencePaper, PipelineState

# Project root: two directories above src/agents/
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent

_CHUNK_WORDS = 400
_CHUNK_OVERLAP = 50
_TOP_K = 12


def _chunk_text(text: str, source: str) -> list[tuple[str, str]]:
    """Split text into overlapping word-count chunks.

    Returns list of (source, chunk_text) tuples.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + _CHUNK_WORDS
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append((source, chunk))
        if end >= len(words):
            break
        start = end - _CHUNK_OVERLAP
    return chunks


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file, skipping pages with no text."""
    reader = pypdf.PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return " ".join(pages)


def _cosine_similarity(query_vec: np.ndarray, chunk_vecs: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a single query vector and a matrix of chunk vectors."""
    query_norm = np.linalg.norm(query_vec)
    chunk_norms = np.linalg.norm(chunk_vecs, axis=1)
    # Avoid division by zero
    denom = chunk_norms * (query_norm if query_norm > 0 else 1.0)
    denom = np.where(denom > 0, denom, 1.0)
    return (chunk_vecs @ query_vec) / denom


def run_paper_rag(state: PipelineState, run_logger) -> PipelineState:
    """Discover PDFs, chunk+embed them, retrieve top chunks, store in state."""
    papers_dir = PROJECT_ROOT / "data" / "papers"
    pdf_paths = sorted(papers_dir.glob("*.pdf"))

    if not pdf_paths:
        print("[WARN] paper_rag: no PDFs found in data/papers/, skipping")
        state["evidence_papers"] = []
        return state

    # Extract text and build chunks
    all_chunks: list[tuple[str, str]] = []  # (source_stem, chunk_text)
    pdf_count = 0
    for pdf_path in pdf_paths:
        try:
            text = _extract_pdf_text(pdf_path)
        except Exception as exc:
            print(f"[WARN] paper_rag: failed to read {pdf_path.name}: {exc}")
            continue
        if not text.strip():
            print(f"[WARN] paper_rag: no text extracted from {pdf_path.name}, skipping")
            continue
        chunks = _chunk_text(text, pdf_path.stem)
        all_chunks.extend(chunks)
        pdf_count += 1

    if not all_chunks:
        print("[WARN] paper_rag: no text could be extracted from any PDF, skipping")
        state["evidence_papers"] = []
        return state

    print(f"[INFO] paper_rag: loaded {len(all_chunks)} chunks from {pdf_count} PDFs")

    # Build OpenAI client for embeddings
    config = state["config"]
    client = create_client(config.base_url, config.api_key)

    chunk_texts = [c[1] for c in all_chunks]

    # Embed chunks and query in a single call so TF-IDF fallback shares vocabulary
    domain_desc = config.pipeline.domain
    all_texts = chunk_texts + [domain_desc]
    all_embeddings = get_embeddings(
        texts=all_texts,
        client=client,
        model=config.embedding.model,
        fallback=config.embedding.fallback,
    )
    chunk_embeddings = all_embeddings[:-1]
    query_embedding = all_embeddings[-1]

    # Cosine similarity: query vs all chunks
    similarities = _cosine_similarity(query_embedding, chunk_embeddings)

    # Take top _TOP_K indices (descending similarity)
    top_k = min(_TOP_K, len(all_chunks))
    top_indices = np.argsort(similarities)[::-1][:top_k]

    retrieved = [
        EvidencePaper(
            title=all_chunks[i][0],
            abstract=all_chunks[i][1],
            year=0,
            citation_count=0,
            fields=[],
        )
        for i in top_indices
    ]

    print(f"[INFO] paper_rag: retrieved {len(retrieved)} chunks for ideator")

    state["evidence_papers"] = retrieved
    return state
