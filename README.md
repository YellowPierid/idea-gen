# AI-Native Productivity App Idea Generator

LangGraph pipeline that generates, evaluates, and ranks AI-native application ideas using multiple LLM agents via OpenRouter.

## Quick Start

```bash
# 1. Install (Python 3.12+ required)
pip install -e ".[dev]"

# 2. Set your OpenRouter API key
export OPENROUTER_API_KEY=your-key          # Linux/Mac
set OPENROUTER_API_KEY=your-key             # Windows

# 3. Validate config and test API connectivity
python -m src.main config-check

# 4. Run the pipeline
python -m src.main run --n_raw 30 --top_k 10 --seed 42

# 5. Inspect outputs
python -m src.main inspect <run_id>

# Or browse directly
ls outputs/runs/
```

## Pipeline

```
Node A:   Ideator         -- Generate 30 raw ideas (3 calls x 10, by user segment)
Node A.5: Selector        -- Diversity-maximizing selection via embedding clustering
Node B:   Recombiner      -- Combine top ideas into 5+ hybrids
Node C:   Gatekeeper      -- Anti-wrapper veto (structured scoring + thresholds)
Node D:   Principles Judge -- Score on 5 AI-native design principles
Node D.5: Pre-Ranker      -- Score feasibility, habit potential, monetization
Node E:   DSR Designer     -- Design Science Research validation protocol
Node F:   Ranker           -- Final ranking + 7-day execution plan
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m src.main run` | Run the full pipeline |
| `python -m src.main run --resume <run_id>` | Resume a failed run |
| `python -m src.main inspect <run_id>` | Inspect a past run |
| `python -m src.main config-check` | Validate config and test connectivity |

### Run Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n_raw` | 30 | Number of raw ideas to generate |
| `--top_k` | 10 | Number of ideas to select after clustering |
| `--seed` | 42 | Random seed for reproducibility |
| `--domain` | productivity | Target domain |
| `--config-path` | config.yaml | Path to config file |

## Configuration

All settings are in `config.yaml`. Key sections:

- **models**: Friendly name to OpenRouter slug mapping
- **agents**: Per-agent model and temperature assignments
- **gatekeeper**: Kill thresholds (Q1>=6, Q2<=3, Q3<=3)
- **pipeline**: Default parameters (domain, n_raw, top_k, etc.)
- **embedding**: Provider and fallback settings

## Output Artifacts

Each run produces files in `outputs/runs/<timestamp>/`:

| File | Description |
|------|-------------|
| `raw_ideas.jsonl` | All generated raw ideas |
| `selected_ideas.jsonl` | Diversity-selected top_k |
| `hybrids.jsonl` | Recombined hybrid ideas |
| `gate_results.jsonl` | Pass/kill results with scores |
| `principle_scores.jsonl` | 5-principle scoring |
| `pre_ranker_scores.jsonl` | Feasibility/habit/monetization |
| `dsr_protocols.md` | Validation protocols (survivors) |
| `final_ranked.md` | Ranked survivors with rationales |
| `next_7_days_plan.md` | Execution plan for #1 idea |
| `run.log.json` | Structured event log |
| `checkpoint.json` | Pipeline state for resume |

## Tests

```bash
# Run all non-LLM tests
pytest tests/ -v -k "not LLM and not Pipeline"

# Run all tests (requires OPENROUTER_API_KEY)
pytest tests/ -v
```

## Requirements

- Python 3.12+
- OpenRouter API key
- Dependencies: langchain, langgraph, openai, pydantic, scikit-learn, click, pyyaml
