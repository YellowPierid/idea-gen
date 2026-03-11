# Plan: Replace paper_fetcher with Manual PDF RAG Pipeline

## Context

The automated `paper_fetcher` node queries Semantic Scholar with fixed queries and consistently returns irrelevant papers. The fix: the user manually curates 5 biology papers as PDFs, and a new `paper_rag` node chunks, embeds, and retrieves relevant passages once per pipeline run, injecting them into the ideator prompt exactly as before.

---

## Decisions Made

| Decision | Choice |
|---|---|
| Paper format | PDF files |
| Paper depth | Full content (chunked + embedded) |
| Retrieval trigger | Once before ideator (not per-LLM-call) |
| PDF location | `data/papers/` auto-discovered |
| Retrieval query | Domain description string from config |
| Embedding | Reuse existing `get_embeddings()` in `src/embeddings.py` |

---

## Architecture

```
[data/papers/*.pdf]
       |
  paper_rag node
  1. Parse PDFs with pypdf
  2. Chunk text (~400 tokens, 50-token overlap)
  3. Embed all chunks via get_embeddings()
  4. Embed query (domain description)
  5. Cosine similarity -> top 12 chunks
  6. Format as EvidencePaper list -> state["evidence_papers"]
       |
   ideator (unchanged - already consumes evidence_papers)
```

---

## Implementation Steps

### Step 1: Add `pypdf` dependency
- Check `requirements.txt` (or `pyproject.toml`) and add `pypdf>=4.0.0`

### Step 2: Create `src/agents/paper_rag.py`
Replace `paper_fetcher.py` logic with:
```python
def run_paper_rag(state: PipelineState) -> dict:
    # 1. Discover PDFs in data/papers/
    # 2. Extract text from each PDF using pypdf
    # 3. Chunk text (~400 tokens, 50-token overlap by word count)
    # 4. Embed all chunks via get_embeddings()
    # 5. Embed query = state["config"]["domain_description"]
    # 6. Cosine similarity, take top 12 chunks
    # 7. Return {"evidence_papers": [EvidencePaper(title=pdf_name, abstract=chunk_text, ...)]}
```
- If `data/papers/` is empty or missing: log `[WARN]` and return `{"evidence_papers": []}` (pipeline continues without evidence)
- Each top chunk becomes one `EvidencePaper` with: `title=<pdf_filename>`, `abstract=<chunk_text>`, `year=0`, `citation_count=0`, `fields=[]`

### Step 3: Update `src/graph.py`
- Replace import: `from agents.paper_fetcher import run_paper_fetcher` -> `from agents.paper_rag import run_paper_rag`
- Replace node registration: `graph.add_node("paper_fetcher", run_paper_fetcher)` -> `graph.add_node("paper_fetcher", run_paper_rag)`
  - Keep the node name `"paper_fetcher"` so all edges and checkpoint logic remain unchanged

### Step 4: Create `data/papers/` directory
- Add `data/papers/.gitkeep` to track the empty directory
- Add `data/papers/*.pdf` to `.gitignore` (PDFs are user-local, not committed)

---

## Critical Files

| File | Action |
|---|---|
| `src/agents/paper_fetcher.py` | Replace entirely with new `paper_rag.py` logic |
| `src/agents/paper_rag.py` | New file |
| `src/graph.py` | Swap import + node registration (name stays same) |
| `src/embeddings.py` | Reuse `get_embeddings()` -- no changes |
| `src/schemas.py` | Reuse `EvidencePaper` -- no changes |
| `requirements.txt` / `pyproject.toml` | Add `pypdf>=4.0.0` |
| `data/papers/` | New directory with `.gitkeep` |

---

## Verification

1. Drop 5 biology PDFs into `data/papers/`
2. Run `python -m src.main run` (or equivalent entry point)
3. Confirm logs show `[INFO] paper_rag: loaded N chunks from 5 PDFs`
4. Confirm logs show `[INFO] paper_rag: retrieved 12 chunks for ideator`
5. Check `outputs/raw_ideas.jsonl` -- ideas should reference biology content from the PDFs
6. Test empty folder: remove PDFs, rerun -- should log `[WARN]` and continue without crashing
