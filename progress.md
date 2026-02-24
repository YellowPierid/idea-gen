# Progress Tracker

## Current State: v3.1 (Two-Tier Memory) TESTED AND WORKING

All v3.0 enhancements + Two-Tier Memory System are coded, tested, and verified via two full pipeline runs. SPEC.md updated to v3.1.

---

## What Was Built

### Core Modules (src/)
| File | Purpose | Status |
|------|---------|--------|
| schemas.py | Pydantic v2 models with validators (IdeaCandidate, GateResult, AngelRescueResult, PrincipleScore, PreRankerScore, DSRProtocol, FinalRanking, UserProfile, SearchConfig, PipelineConfig, PipelineState) | Done |
| config.py | YAML loader, model name resolution, agent config lookup, user_profile + search parsing | Done |
| logging_utils.py | RunLogger: console progress + JSON file log | Done |
| storage.py | OutputStore: JSONL/Markdown writing, checkpoint save/load, global history persistence (JSONL + numpy) | Done |
| llm.py | OpenRouter client, structured JSON parsing, schema repair fallback (glm-4.7-flash) | Done |
| embeddings.py | OpenRouter embeddings + TF-IDF fallback | Done |
| scoring.py | Gatekeeper thresholds, score normalization, final aggregation | Done |
| prompt_utils.py | format_user_context() shared utility for ideator + pre_ranker | Done (v3.0) |
| search.py | DuckDuckGo market evidence search with graceful fallback | Done (v3.0) |
| graph.py | LangGraph wiring: 10 nodes (added user_review + update_themes), conditional retry, checkpointing | Done |
| main.py | Click CLI: run (--no-pause), inspect, config-check | Done |

### Agent Nodes (src/agents/)
| File | Node | Model | Purpose |
|------|------|-------|---------|
| ideator.py | A | grok-4.1-fast | 3x10 divergent generation by user segment + user_context + memory (Tier 1 hard filter + Tier 2 soft prompt) + backfill |
| selector.py | A.5 | (embedding) | K-means clustering for diversity selection |
| user_review.py | A.5b | (CLI) | Interactive veto/star review (--no-pause to skip) |
| recombiner.py | B | deepseek-v3.2 | Hybrid generation (min 5) with retry |
| gatekeeper.py | C | gpt-oss-120b + grok-4.1-fast | Anti-wrapper veto + Angel's Rescue + starred bypass |
| principles_judge.py | D | gpt-oss-120b | 5-principle scoring (0-2 each) |
| pre_ranker.py | D.5 | gpt-oss-120b | Feasibility/habit/monetization + market search + user_context |
| dsr_designer.py | E | deepseek-v3.2 | DSR validation protocols |
| ranker.py | F | gpt-oss-120b | Final aggregation + 7-day plan |

### Prompt Templates (src/prompts/)
16 files: system + user for each of the 8 LLM-calling agents (7 original + angel_rescue).
`src/prompts/context/past_themes.md` -- auto-populated placeholder for Tier 2 soft memory (overused theme list).

### Tests (tests/)
- test_schema_validation.py -- schema parsing + LLM integration tests
- test_gatekeeper_logic.py -- threshold logic + edge cases (10 tests)
- test_ranker_stability.py -- score aggregation math (7 tests)
- **25 passed, 2 skipped** (re-verified 2026-02-04 after v3.1 changes).

---

## Key Decisions Made

1. **Python 3.12 venv** at `.venv/` -- all deps installed via `pip install -e ".[dev]"`
2. **Pyright warnings are expected** -- IDE not configured for venv interpreter; all imports resolve at runtime
3. **PipelineState uses TypedDict** -- compatible with LangGraph state passing
4. **GateLLMResponse intermediate schema** in gatekeeper.py -- LLM outputs scores without status/kill_reason; those are set programmatically by apply_gate_thresholds()
5. **RankerLLMResponse intermediate schema** in ranker.py -- LLM provides rationales + 7-day plan text; final scores computed programmatically
6. **Extra state keys** `_seven_day_plan` and `_ranker_notes` -- stored in state dict for output generation (not in TypedDict definition)
7. **Sequential LLM calls** -- no parallelism, per spec constraint
8. **Schema repair** routes to glm-4.7-flash immediately on failure (no primary retry)
9. **Checkpoint after every node** via _wrap_node in graph.py
10. **Conditional retry** after gatekeeper: if all killed and retry_count < max_retries, loops back to ideator with different user segments
11. **API key via .env file** -- added python-dotenv; config.py calls load_dotenv() before reading env vars
12. **Schema repair model updated** -- switched to glm-4.7-flash (z-ai/glm-4.7-flash) for cost-efficient JSON repair
13. **Angel's Rescue** (v3.0): grok-4.1-fast at temp 0.7. Max 1 attempt per idea, no recursion. Rescued ideas are re-scored through gatekeeper; if still KILL, kill is confirmed.
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
26. **RunLogger bug fix** (2026-02-04): `_update_past_themes` in graph.py used printf-style `run_logger.info("...%d", val)` but RunLogger only accepts a single string. Converted to f-strings. Also fixed `run_logger.warning()` call -- method is `warn()`, not `warning()`.
27. **scikit-learn not pre-installed**: Despite being declared in pyproject.toml, `sklearn` was missing at runtime. Installed manually (`pip install scikit-learn`). Root cause: environment was not installed via `pip install -e .`.
28. **SPEC.md updated to v3.1**: Added MemoryConfig schema (7.9), Node G (Update Themes), memory config block, global_history in repo structure, 6 decision log entries (#38-43).
29. **LLM model swap** (2026-02-04): Replaced all models to improve idea generation quality. Old -> New: qwen-72b -> grok-4.1-fast (creative agents), qwen-72b -> deepseek-v3.2 (recombiner), llama-70b -> gpt-oss-120b (all judges/rankers), deepseek-r1-32b -> deepseek-v3.2 (DSR designer), qwen-14b -> glm-4.7-flash (schema repair). Config-only change -- no Python code modified. Rationale: previous models produced weak/generic ideas; new models selected for stronger creative divergence (Grok 4.1 Fast) and better reasoning (DeepSeek V3.2, GPT-OSS 120B).

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

### Status: TESTED AND WORKING

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

### Status: TESTED AND WORKING

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

### Testing Results (2026-02-04)

1. **Unit tests:** 25 passed, 2 skipped (`python -m pytest tests/ -x -q`)
2. **Config check:** All model mappings valid, API connection OK, 16 prompt templates found
3. **Pipeline run 1** (`20260204_141137`): All nodes completed. 9 ideas generated, 5 survived gatekeeper (5 rescued by angel). Failed at `update_themes` due to `RunLogger.info()` printf-style formatting bug.
4. **Bug fix:** `graph.py` lines 171-177, 212 -- converted `RunLogger.info("... %d", val)` to f-strings. Also fixed `run_logger.warning()` (method is `warn`, not `warning`).
5. **Pipeline run 2** (`20260204_142313`): Full success (exit code 0). 9 ideas generated, Tier 1 memory filtered 1 duplicate (`ThesisMaster`, similarity 0.856), backfill generated 1 replacement. 4 survivors ranked. `update_themes` wrote `past_themes.md` (18 ideas summarized). Top idea: ProjectLitMap (score 3.100).

### Next Steps

1. Write FOR_YELLOW.md
2. Run pipeline with new LLMs to verify all models work via OpenRouter
3. Implement v3.2 (LangSmith Tracing & Evaluation)

---

## LLM Model Swap -- COMPLETE (config-only)

### Status: CONFIG UPDATED, AWAITING FIRST RUN

### Motivation
Previous models (Qwen 2.5 72B, Llama 3.1 70B, DeepSeek R1 32B) produced weak/generic ideas. Switched to models with stronger creative and reasoning capabilities.

### Model Mapping (Old -> New)

| Friendly Name | Old OpenRouter Slug | New OpenRouter Slug |
|---------------|---------------------|---------------------|
| grok-4.1-fast | qwen/qwen-2.5-72b-instruct | x-ai/grok-4.1-fast |
| deepseek-v3.2 | qwen/qwen-2.5-72b-instruct (recombiner) / deepseek/deepseek-r1-distill-qwen-32b (DSR) | deepseek/deepseek-v3.2 |
| gpt-oss-120b | meta-llama/llama-3.1-70b-instruct | openai/gpt-oss-120b |
| glm-4.7-flash | qwen/qwen3-14b | z-ai/glm-4.7-flash |

### Agent Assignments

| Agent | Old Model | New Model | Old Temp | New Temp |
|-------|-----------|-----------|----------|----------|
| ideator | qwen-72b | grok-4.1-fast | 0.80 | 0.85 |
| recombiner | qwen-72b | deepseek-v3.2 | 0.65 | 0.60 |
| gatekeeper | llama-70b | gpt-oss-120b | 0.25 | 0.20 |
| principles_judge | llama-70b | gpt-oss-120b | 0.20 | 0.18 |
| pre_ranker | llama-70b | gpt-oss-120b | 0.20 | 0.20 |
| dsr_designer | deepseek-r1-32b | deepseek-v3.2 | 0.25 | 0.25 |
| ranker | llama-70b | gpt-oss-120b | 0.15 | 0.15 |
| schema_repair | qwen-14b | glm-4.7-flash | 0.00 | 0.00 |
| angel_rescue | qwen-72b | grok-4.1-fast | 0.70 | 0.70 |

### Files Changed
- `config.yaml` -- model mappings and agent assignments (only file changed)

### What Did NOT Change
- No Python code changes. Architecture is fully config-driven.
- `.env` -- same OPENROUTER_API_KEY, same base URL
- Embedding model unchanged (openai/text-embedding-3-small)

---

## Prompt Quality Improvements -- COMPLETE

### Status: IMPLEMENTED AND VERIFIED

### Problem
Prompts were too loose. Ideator had no anti-examples, no concrete pain points, vague "AI-native" definition. Gatekeeper had no scoring anchors. Recombiner got raw JSON dumps with no combination guidance. Result: LLMs defaulted to safe, generic outputs regardless of model choice.

### Changes Made

1. [x] **Ideator system prompt** (`src/prompts/ideator_system.md`) -- Added 2 anti-examples (AI Meeting Summarizer, Smart To-Do List) with failure explanations, 1 good example (CommitGraph), sharpened "AI magic moment" definition (3-part test: accumulated context + not ChatGPT-replicable + improves with use), added structured hook loop requirements (trigger, action, reward, investment)
2. [x] **Ideator user prompt** (`src/prompts/ideator_user.md`) -- Replaced generic segment labels with pain-point framing per segment (specific frustrations/workflow gaps), added competitive landscape (Notion, Linear, Obsidian, Granola, etc.), added explicit anti-pattern instruction (no summarizers, chatbots, generic writing assistants, or "user types -> LLM responds" loops)
3. [x] **Gatekeeper system prompt** (`src/prompts/gatekeeper_system.md`) -- Added 3-tier calibration anchors for Q1/Q2/Q3 scoring (concrete score examples at low/mid/high), added heuristic: "if replicable with ChatGPT custom instruction + spreadsheet, score Q1 >= 7"
4. [x] **Recombiner system prompt** (`src/prompts/recombiner_system.md`) -- Required compounding_advantage field to answer 3 questions: what data accumulates, how it improves the product, why a competitor can't replicate in < 6 months. Added: "if you cannot answer all three, do not include the hybrid"
5. [x] **Recombiner user prompt** (`src/prompts/recombiner_user.md`) -- Added combination strategy directive: look for ideas serving same user at different workflow moments, shared data layer, avoid cross-segment Frankensteins
6. [x] **Verify** -- config-check passes (all 16 templates found, API OK), 25 unit tests passed, 2 skipped

### Additional fix
- `src/main.py` line 212: Fixed config-check connectivity test model reference from old `qwen-14b` to `glm-4.7-flash` (broken since model swap).

### Scope
- 5 prompt .md files changed. 1 Python file changed (1-line fix in main.py). No schema changes, no config changes.
- Output format instructions in each prompt remain identical so structured parsing continues to work.

### Full plan file: `~/.claude/plans/happy-swinging-cerf.md`

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
