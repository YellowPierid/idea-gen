# Progress Tracker

## Current State: v3.1 (Two-Tier Memory) CODE COMPLETE, NEEDS TESTING

All v3.0 enhancements + Two-Tier Memory System are coded. All imports verified at runtime (AST parse + runtime import checks). Existing tests not yet re-run. Next session: run tests, then do a full pipeline run.

---

## What Was Built

### Core Modules (src/)
| File | Purpose | Status |
|------|---------|--------|
| schemas.py | Pydantic v2 models with validators (IdeaCandidate, GateResult, AngelRescueResult, PrincipleScore, PreRankerScore, DSRProtocol, FinalRanking, UserProfile, SearchConfig, PipelineConfig, PipelineState) | Done |
| config.py | YAML loader, model name resolution, agent config lookup, user_profile + search parsing | Done |
| logging_utils.py | RunLogger: console progress + JSON file log | Done |
| storage.py | OutputStore: JSONL/Markdown writing, checkpoint save/load, global history persistence (JSONL + numpy) | Done |
| llm.py | OpenRouter client, structured JSON parsing, schema repair fallback (qwen-14b) | Done |
| embeddings.py | OpenRouter embeddings + TF-IDF fallback | Done |
| scoring.py | Gatekeeper thresholds, score normalization, final aggregation | Done |
| prompt_utils.py | format_user_context() shared utility for ideator + pre_ranker | Done (v3.0) |
| search.py | DuckDuckGo market evidence search with graceful fallback | Done (v3.0) |
| graph.py | LangGraph wiring: 10 nodes (added user_review + update_themes), conditional retry, checkpointing | Done |
| main.py | Click CLI: run (--no-pause), inspect, config-check | Done |

### Agent Nodes (src/agents/)
| File | Node | Model | Purpose |
|------|------|-------|---------|
| ideator.py | A | qwen-72b | 3x10 divergent generation by user segment + user_context + memory (Tier 1 hard filter + Tier 2 soft prompt) + backfill |
| selector.py | A.5 | (embedding) | K-means clustering for diversity selection |
| user_review.py | A.5b | (CLI) | Interactive veto/star review (--no-pause to skip) |
| recombiner.py | B | qwen-72b | Hybrid generation (min 5) with retry |
| gatekeeper.py | C | llama-70b + qwen-72b | Anti-wrapper veto + Angel's Rescue + starred bypass |
| principles_judge.py | D | llama-70b | 5-principle scoring (0-2 each) |
| pre_ranker.py | D.5 | llama-70b | Feasibility/habit/monetization + market search + user_context |
| dsr_designer.py | E | deepseek-r1-32b | DSR validation protocols |
| ranker.py | F | llama-70b | Final aggregation + 7-day plan |

### Prompt Templates (src/prompts/)
16 files: system + user for each of the 8 LLM-calling agents (7 original + angel_rescue).
`src/prompts/context/past_themes.md` -- auto-populated placeholder for Tier 2 soft memory (overused theme list).

### Tests (tests/)
- test_schema_validation.py -- schema parsing + LLM integration tests
- test_gatekeeper_logic.py -- threshold logic + edge cases (10 tests)
- test_ranker_stability.py -- score aggregation math (7 tests)
- **23 non-LLM tests passed previously.** Need to re-run after v3.0 changes.

---

## Key Decisions Made

1. **Python 3.12 venv** at `.venv/` -- all deps installed via `pip install -e ".[dev]"`
2. **Pyright warnings are expected** -- IDE not configured for venv interpreter; all imports resolve at runtime
3. **PipelineState uses TypedDict** -- compatible with LangGraph state passing
4. **GateLLMResponse intermediate schema** in gatekeeper.py -- LLM outputs scores without status/kill_reason; those are set programmatically by apply_gate_thresholds()
5. **RankerLLMResponse intermediate schema** in ranker.py -- LLM provides rationales + 7-day plan text; final scores computed programmatically
6. **Extra state keys** `_seven_day_plan` and `_ranker_notes` -- stored in state dict for output generation (not in TypedDict definition)
7. **Sequential LLM calls** -- no parallelism, per spec constraint
8. **Schema repair** routes to qwen-14b immediately on failure (no primary retry)
9. **Checkpoint after every node** via _wrap_node in graph.py
10. **Conditional retry** after gatekeeper: if all killed and retry_count < max_retries, loops back to ideator with different user segments
11. **API key via .env file** -- added python-dotenv; config.py calls load_dotenv() before reading env vars
12. **Schema repair model updated** -- qwen/qwen-2.5-14b-instruct no longer on OpenRouter; replaced with qwen/qwen3-14b
13. **Angel's Rescue** (v3.0): qwen-72b at temp 0.7. Max 1 attempt per idea, no recursion. Rescued ideas are re-scored through gatekeeper; if still KILL, kill is confirmed.
14. **Starred ideas** (v3.0): Bypass gatekeeper kill entirely. Scored for data but immune to KILL. Angel's Rescue skipped for starred ideas.
15. **User profile** (v3.0): Fully optional. format_user_context() returns empty string if no profile. Injected into ideator system prompt and pre_ranker user prompt.
16. **Market search** (v3.0): DuckDuckGo (free, no API key). Graceful fallback -- returns None on failure, pre_ranker falls back to LLM-only scoring.
17. **User Review node** (v3.0): Separate LangGraph node (not inline in selector). Gets its own checkpoint. Passthrough when interactive=False.
18. **GateResult.starred field** (v3.0): Added boolean to track which ideas were user-starred, for data completeness in gate_results.jsonl.
19. **duckduckgo-search 8.1.1** installed via pyproject.toml dependency.
20. **Two-Tier Memory -- Tier 1 (Hard)**: Embedding cosine similarity against global history. Threshold 0.85. Ideas above threshold are silently killed. Intra-batch detection included (each accepted idea is added to history in-memory so later ideas in same batch are checked against earlier ones).
21. **Two-Tier Memory -- Tier 2 (Soft)**: `past_themes.md` injected into ideator system prompt via `{past_themes}` template variable. Auto-generated by `update_themes` node after ranker when history has 10+ ideas. LLM summarizes overused themes into a bulleted list.
22. **Global history storage**: Dual-file approach -- `idea_history.jsonl` (human-readable records with name+text) + `idea_vectors.npy` (numpy array for efficient cosine similarity). Sanity check on load resets both files if record/vector counts mismatch.
23. **Backfill logic**: When Tier 1 filter removes ideas below target count, up to 2 backfill rounds cycle through segments to generate replacement ideas. Each backfill batch also passes through the novelty filter.
24. **update_themes node**: Runs after ranker, before END. Non-fatal -- wrapped in try/except so a failed LLM call does not crash the pipeline. Only fires when 10+ ideas exist in global history.
25. **Pipeline flow changed**: `ranker -> update_themes -> END` (was `ranker -> END`).

---

## Key Files for Resuming Work

1. `SPEC.md` -- full specification (authoritative)
2. `config.yaml` -- all pipeline configuration
3. `src/graph.py` -- pipeline wiring (start here to understand flow)
4. `src/schemas.py` -- all data models
5. `src/main.py` -- CLI entry point
6. `.env` -- API key (do not commit)

---

## v3.0 Enhancements -- COMPLETE

### Status: ALL CODE IMPLEMENTED, NEEDS TESTING

All 6 v3.0 enhancements are coded and import-verified:

| Enhancement | Files Changed | Status |
|------------|---------------|--------|
| Angel's Rescue | gatekeeper.py, angel_rescue_system.md, angel_rescue_user.md, schemas.py (AngelRescueResult) | Done |
| User Profile | schemas.py (UserProfile), config.py, config.yaml, prompt_utils.py, ideator.py, ideator_system.md, pre_ranker.py, pre_ranker_user.md | Done |
| Interactive Review | user_review.py, graph.py, main.py (--no-pause), schemas.py (PipelineState) | Done |
| Market Search | search.py, pre_ranker.py, pre_ranker_system.md, pre_ranker_user.md, pyproject.toml | Done |
| Starred Ideas | user_review.py, gatekeeper.py, schemas.py (GateResult.starred), main.py | Done |
| Config Extensions | config.yaml (angel_rescue, user_profile, search), config.py, schemas.py (SearchConfig) | Done |

### Verification performed:
- `from src.schemas import AngelRescueResult, UserProfile, SearchConfig, PipelineState` -- OK
- `from src.prompt_utils import format_user_context` -- OK
- `from src.search import search_market_evidence` -- OK
- `from src.agents.user_review import run_user_review` -- OK
- `from src.config import load_config; c = load_config()` -- OK (profile, search, angel_rescue all parsed)
- `from src.graph import build_graph` -- OK

---

## v3.1 Two-Tier Memory System -- COMPLETE

### Status: ALL CODE IMPLEMENTED, NEEDS TESTING

| Component | Files Changed | Status |
|-----------|---------------|--------|
| MemoryConfig schema | schemas.py (MemoryConfig class, PipelineConfig.memory field) | Done |
| Config loading | config.py (memory section parsing), config.yaml (memory block) | Done |
| Global history persistence | storage.py (load_global_history, save_global_history) | Done |
| Tier 1: Hard novelty filter | ideator.py (_filter_duplicates, _idea_to_text, backfill loop) | Done |
| Tier 2: Soft prompt injection | ideator.py (_load_past_themes), ideator_system.md ({past_themes} slot) | Done |
| Theme auto-update node | graph.py (_update_past_themes, update_themes node wired after ranker) | Done |
| Placeholder file | src/prompts/context/past_themes.md (empty, auto-populated after runs) | Done |

### Verification performed:
- AST syntax check on all 5 modified Python files -- all passed
- `from src.schemas import MemoryConfig` -- OK
- `from src.storage import load_global_history, save_global_history` -- OK
- `from src.agents.ideator import run_ideator, PAST_THEMES_PATH` -- OK
- `from src.config import load_config; c = load_config(); c.memory.similarity_threshold` returns 0.85 -- OK
- `c.memory.history_dir` returns `./outputs/global_history` -- OK

### Architecture:
```
Pipeline flow:
ideator (Tier 1 filter + Tier 2 prompt + backfill)
  -> selector -> user_review -> recombiner -> gatekeeper
  -> [retry loop if all killed]
  -> principles_judge -> pre_ranker -> dsr_designer -> ranker
  -> update_themes (Tier 2 refresh, 10+ ideas threshold)
  -> END

Storage:
outputs/global_history/
  idea_history.jsonl   -- {name, text} per idea (append-on-write, full-overwrite)
  idea_vectors.npy     -- numpy float array, one row per idea

Prompt injection:
src/prompts/context/past_themes.md -> {past_themes} in ideator_system.md
```

### Next Steps

1. Run existing tests: `python -m pytest tests/ -x -q`
2. Run config-check: `python -m src.main config-check`
3. Do a full pipeline run: `python -m src.main run --no-pause --n_raw 9 --top_k 3 --seed 42`
4. Review outputs in `outputs/runs/` and `outputs/global_history/`
5. Run a second pipeline run to verify memory system filters duplicates
6. Write FOR_YELLOW.md if pipeline runs successfully

---

## v3.2 LangSmith Tracing & Evaluation -- PLANNED

### Status: PLAN COMPLETE, NOT YET IMPLEMENTED

### Problem
Pipeline makes ~40 LLM calls per run via direct OpenAI SDK (openai.OpenAI -> OpenRouter). No observability into individual calls: no latency, token usage, prompt/response logging, or scoring consistency tracking. LangSmith 0.6.7 is installed but unconfigured. Auto-tracing only captures LangGraph state transitions, NOT individual LLM calls, because we use raw `client.chat.completions.create()` instead of LangChain's ChatOpenAI.

### Approach: `wrap_openai()` + `@traceable`

**Chosen:** `langsmith.wrappers.wrap_openai()` patches the OpenAI client to auto-trace all completions calls. Combined with `@traceable` on the node wrapper for hierarchical traces (pipeline -> node -> LLM call).

**Rejected alternatives:**
- ChatOpenAI migration: requires rewriting all agent calls. Too invasive.
- @traceable on every function: more touch points, manual metadata needed.

### Key Decisions
26. **LangSmith tracing via wrap_openai()**: 1-line change in `create_client()` in llm.py. Auto-captures model, temperature, messages, response, latency, token counts on every LLM call.
27. **Node-level trace hierarchy**: `@traceable(name=node_name, run_type="chain")` on `_wrap_node()` in graph.py. Nests LLM calls under their parent node in the trace tree.
28. **Eval datasets from future runs**: No past run data exists. Evaluation module collects data from traced runs via `langsmith.Client().list_runs()`. Run pipeline 2-3 times first, then build datasets.
29. **Separate eval module**: New `src/evaluation/` package (4 files). Isolated from pipeline logic, zero changes to agent code.

### Changes Required

**Modified files (3):**
| File | Change |
|------|--------|
| `.env` | Add LANGCHAIN_TRACING_V2, LANGCHAIN_ENDPOINT, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT |
| `src/llm.py` | Add `from langsmith.wrappers import wrap_openai` + wrap client in `create_client()` (~2 lines) |
| `src/graph.py` | Add `from langsmith import traceable` + `@traceable` decorator on `_wrap_node()` (~3 lines) |

**New files (4):**
| File | Purpose |
|------|---------|
| `src/evaluation/__init__.py` | Package marker |
| `src/evaluation/datasets.py` | Build eval datasets from traced runs via LangSmith API |
| `src/evaluation/evaluators.py` | Custom evaluators: gatekeeper consistency, principles alignment |
| `src/evaluation/run_eval.py` | CLI entry point for running evals |

### Verification Plan
1. `uv run python -m src.main config-check` -- confirms wrapped client works
2. `uv run python -m src.main run --n_raw 5 --top_k 3 --no-pause` -- small pipeline run
3. Check smith.langchain.com dashboard for nested traces with full LLM call metadata
4. After 2-3 runs: `uv run python -m src.evaluation.datasets` to build eval datasets
5. `uv run python -m src.evaluation.run_eval` to run evals

### Full plan file: `~/.claude/plans/spicy-giggling-backus.md`
