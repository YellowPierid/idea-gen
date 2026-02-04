# AI-Native Idea Generator Pipeline - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete LangGraph pipeline that generates, evaluates, and ranks AI-native app ideas via OpenRouter LLMs.

**Architecture:** Sequential LangGraph nodes (A -> A.5 -> B -> C -> D -> D.5 -> E -> F) with file-based checkpointing, JSONL/Markdown outputs, and a CLI interface. OpenRouter provides all LLM/embedding calls with schema repair fallback.

**Tech Stack:** Python 3.11+, LangChain, LangGraph, Pydantic v2, OpenAI client (OpenRouter-compatible), scikit-learn (TF-IDF fallback), PyYAML, Click (CLI)

---

## Task 1: Project Scaffolding + Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/agents/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "idea-gen"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.3.0",
    "langgraph>=0.2.0",
    "langchain-openai>=0.2.0",
    "openai>=1.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "click>=8.0",
    "scikit-learn>=1.3.0",
    "numpy>=1.24.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
```

**Step 2: Create config.yaml** (exact content from SPEC section 9)

**Step 3: Create empty `__init__.py` files for `src/`, `src/agents/`, `tests/`**

**Step 4: Install dependencies**

Run: `pip install -e ".[dev]"`

**Step 5: Verify installation**

Run: `python -c "import langchain; import langgraph; import pydantic; print('OK')"`

---

## Task 2: Pydantic Schemas (`src/schemas.py`)

**Files:**
- Create: `src/schemas.py`

All data models from SPEC section 7: IdeaCandidate, GateResult, PrincipleScore, PreRankerScore, ReservationTest, DSRProtocol, FinalRanking, PipelineState, PipelineConfig, CheckpointData.

**Verify:** `python -c "from src.schemas import IdeaCandidate, GateResult, PipelineState; print('OK')"`

---

## Task 3: Configuration Loading (`src/config.py`)

**Files:**
- Create: `src/config.py`

Load config.yaml, map friendly model names to OpenRouter slugs, resolve API key from env var, return typed PipelineConfig.

**Verify:** `python -c "from src.config import load_config; c = load_config(); print(c.pipeline.domain)"`

---

## Task 4: Structured Logging (`src/logging_utils.py`)

**Files:**
- Create: `src/logging_utils.py`

RunLogger class: console progress + JSON file log. Events: node_start, node_end, llm_call, schema_validation, schema_repair, kill, pass.

**Verify:** Instantiate RunLogger, log a test event, check JSON output.

---

## Task 5: Storage + Checkpointing (`src/storage.py`)

**Files:**
- Create: `src/storage.py`

OutputStore class: create run directory, write JSONL, write Markdown, save/load checkpoint.

**Verify:** `python -c "from src.storage import OutputStore; s = OutputStore('./outputs'); print(s.run_dir)"`

---

## Task 6: LLM Client + Schema Repair (`src/llm.py`)

**Files:**
- Create: `src/llm.py`

OpenRouter client wrapper using openai library. Functions: `call_llm(model, temperature, system_prompt, user_prompt) -> str` and `call_llm_structured(model, temperature, system_prompt, user_prompt, schema) -> BaseModel` with schema repair fallback to qwen-14b.

**Verify:** Requires API key. Manual test with config-check later.

---

## Task 7: Embeddings Client (`src/embeddings.py`)

**Files:**
- Create: `src/embeddings.py`

`get_embeddings(texts, config) -> np.ndarray` -- OpenRouter primary, TF-IDF fallback.

**Verify:** `python -c "from src.embeddings import get_embeddings_tfidf; print(get_embeddings_tfidf(['hello', 'world']).shape)"`

---

## Task 8: Scoring Utilities (`src/scoring.py`)

**Files:**
- Create: `src/scoring.py`

Gatekeeper threshold logic (apply_gate_thresholds), score normalization, final score aggregation.

**Verify:** Unit-test the threshold logic with known inputs inline.

---

## Task 9: Prompt Templates (all 14 files)

**Files:**
- Create: `src/prompts/ideator_system.md`
- Create: `src/prompts/ideator_user.md`
- Create: `src/prompts/recombiner_system.md`
- Create: `src/prompts/recombiner_user.md`
- Create: `src/prompts/gatekeeper_system.md`
- Create: `src/prompts/gatekeeper_user.md`
- Create: `src/prompts/principles_judge_system.md`
- Create: `src/prompts/principles_judge_user.md`
- Create: `src/prompts/pre_ranker_system.md`
- Create: `src/prompts/pre_ranker_user.md`
- Create: `src/prompts/dsr_designer_system.md`
- Create: `src/prompts/dsr_designer_user.md`
- Create: `src/prompts/ranker_system.md`
- Create: `src/prompts/ranker_user.md`

Each uses LangChain `{variable}` syntax. System prompts define the agent role; user prompts contain the per-call data.

---

## Task 10: Node A - Ideator Agent (`src/agents/ideator.py`)

**Files:**
- Create: `src/agents/ideator.py`

`run_ideator(state: PipelineState) -> PipelineState` -- 3 LLM calls (one per user segment), n_raw/3 ideas each, schema validation + repair, returns updated state with raw_ideas.

---

## Task 11: Node A.5 - Selector Agent (`src/agents/selector.py`)

**Files:**
- Create: `src/agents/selector.py`

`run_selector(state: PipelineState) -> PipelineState` -- embed ideas, k-means cluster, pick closest to each centroid. Returns state with selected_ideas.

---

## Task 12: Node B - Recombiner Agent (`src/agents/recombiner.py`)

**Files:**
- Create: `src/agents/recombiner.py`

`run_recombiner(state: PipelineState) -> PipelineState` -- single LLM call producing min 5 hybrids, retry once if fewer. Returns state with hybrids + all_candidates.

---

## Task 13: Node C - Gatekeeper Agent (`src/agents/gatekeeper.py`)

**Files:**
- Create: `src/agents/gatekeeper.py`

`run_gatekeeper(state: PipelineState) -> PipelineState` -- 1 LLM call per candidate, structured scoring, programmatic thresholds via scoring.py. Returns state with gate_results + survivors.

---

## Task 14: Node D - Principles Judge Agent (`src/agents/principles_judge.py`)

**Files:**
- Create: `src/agents/principles_judge.py`

`run_principles_judge(state: PipelineState) -> PipelineState` -- 1 call per survivor, 5 principles scored 0-2 each. Returns state with principle_scores.

---

## Task 15: Node D.5 - Pre-Ranker Agent (`src/agents/pre_ranker.py`)

**Files:**
- Create: `src/agents/pre_ranker.py`

`run_pre_ranker(state: PipelineState) -> PipelineState` -- 1 call per survivor, 3 dimensions scored 0-2 each. Returns state with pre_ranker_scores.

---

## Task 16: Node E - DSR Designer Agent (`src/agents/dsr_designer.py`)

**Files:**
- Create: `src/agents/dsr_designer.py`

`run_dsr_designer(state: PipelineState) -> PipelineState` -- 1 call per survivor, produces DSRProtocol. Returns state with dsr_protocols.

---

## Task 17: Node F - Ranker Agent (`src/agents/ranker.py`)

**Files:**
- Create: `src/agents/ranker.py`

`run_ranker(state: PipelineState) -> PipelineState` -- aggregate scores (normalize 0-1, equal weights), rank, generate 7-day plan for #1. Returns state with final_ranking.

---

## Task 18: LangGraph Definition (`src/graph.py`)

**Files:**
- Create: `src/graph.py`

Wire all nodes: ideator -> selector -> recombiner -> gatekeeper -> (conditional: retry or continue) -> principles_judge -> pre_ranker -> dsr_designer -> ranker. Checkpoint after each node.

---

## Task 19: CLI Entry Point (`src/main.py`)

**Files:**
- Create: `src/main.py`

Click CLI with 3 commands: `run` (--n_raw, --top_k, --seed, --domain, --resume), `inspect` (run_id), `config-check`.

**Verify:** `python -m src.main config-check`

---

## Task 20: Integration Tests

**Files:**
- Create: `tests/test_schema_validation.py`
- Create: `tests/test_gatekeeper_logic.py`
- Create: `tests/test_ranker_stability.py`

Per SPEC section 11. All require OPENROUTER_API_KEY.

---

## Task 21: README.md

**Files:**
- Create: `README.md`

Quick start guide per SPEC Appendix B.

---

## Execution Order

Tasks 1-8 are foundation (no LLM calls needed to verify).
Task 9 is prompts (pure text).
Tasks 10-17 are agents (each depends on schemas + llm + prompts).
Task 18 wires it all together.
Task 19 adds CLI.
Tasks 20-21 are testing and docs.

**Critical path:** 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10-17 -> 18 -> 19 -> 20 -> 21
