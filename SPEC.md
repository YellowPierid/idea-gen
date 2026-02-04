# AI-Native Productivity App Idea Generator

## Specification Document

**Version:** 3.0
**Tech Stack:** Python, LangChain, LangGraph, OpenRouter
**Target:** Solo developer MVP (4-week timeline)

---

## 1. Overview

### 1.1 Role
Claude Code acting as a senior AI product researcher + agentic systems engineer, building a production-quality LangGraph workflow that generates and evaluates AI-native app ideas.

### 1.2 Objective
Implement an agentic pipeline that:
1. Generates many app ideas across configurable domains (divergent phase)
2. Selects diverse top ideas via embedding-based clustering
3. Recombines and sharpens top ideas (convergent creativity)
4. Applies a hard "anti-wrapper" moat gate with structured scoring and programmatic thresholds (veto)
5. Scores survivors using the Five Core Design Principles for AI-Native Applications
6. Scores survivors on feasibility, habit potential, and monetization plausibility (pre-ranking)
7. Produces a Design Science Research (DSR) validation protocol per surviving idea
8. Outputs ranked finalists + a "next-7-days execution plan" for the #1 idea

---

## 2. Domain Scope

### 2.1 Multi-Domain Support
The pipeline is parameterized by domain. Prompts, user segments, and evaluation criteria all adapt to the configured domain. The default domain is "productivity".

Supported domain examples:
- **productivity** (default): planning, writing, decision-making, meeting workflows, project execution, personal organization, learning-for-work
- Other domains (health, education, finance, etc.) work via parameterized prompts

### 2.2 Default Target Users (Productivity Domain)
- Knowledge workers
- Solopreneurs / Freelancers
- Students / Researchers
- Managers
- Creators

**Exclusion:** NOT children-focused applications

### 2.3 Core Requirement
The idea must be **AI-native** (LLM reasoning/agents/personalization) -- NOT a thin wrapper.

### 2.4 Excluded Topics
- Politics
- Dating
- Explicit medical diagnosis

### 2.5 User Profile (Optional)

The pipeline accepts an optional user profile that biases idea generation and feasibility scoring toward the developer's strengths.

**Profile Fields:**

- `skills` -- technical and domain skills (e.g., "Python", "medical background")
- `stack` -- preferred tech stack (e.g., "Python", "LangGraph", "OpenRouter")
- `past_projects` -- relevant past work (e.g., "AI diagnosis assistant")

**Usage:**

- Node A (Ideator): Prioritizes ideas leveraging the user's "unfair advantages"
- Node D.5 (Pre-Ranker): Feasibility scoring accounts for stack alignment and domain expertise
- If no profile is configured, all nodes fall back to generic behavior

---

## 3. Hard Constraints

| Constraint | Requirement |
|------------|-------------|
| Development Timeline | Solo-dev MVP feasible in 4 weeks |
| Tech Stack | Python (Streamlit optional later, NOT required now) |
| LLM Provider | OpenRouter (OpenAI-compatible API) |
| Validation | Must support "Wizard-of-Oz" validation path (manual backend acceptable) |
| Execution | Must run locally from CLI |
| Output Format | Deterministic artifacts (JSON/Markdown) |
| Reproducibility | Best-effort seeding: seed local randomness, log all prompts/responses, accept LLM non-determinism |
| Processing | Sequential LLM calls (no parallelism). One call per idea per node. |

---

## 4. Repository Structure

```
project-root/
+-- README.md
+-- pyproject.toml
+-- config.yaml                  # All pipeline configuration
+-- src/
|   +-- __init__.py
|   +-- main.py                  # CLI entry (run, inspect, config-check)
|   +-- graph.py                 # LangGraph definition
|   +-- config.py                # Config loading + model name mapping
|   +-- schemas.py               # Pydantic models for I/O
|   +-- scoring.py               # Rubrics + aggregation + gatekeeper thresholds
|   +-- storage.py               # File-based output store + checkpointing
|   +-- llm.py                   # OpenRouter client + schema repair fallback
|   +-- embeddings.py            # Embedding client (OpenRouter + TF-IDF fallback)
|   +-- prompt_utils.py          # Shared user-context formatting
|   +-- search.py                # DuckDuckGo market evidence search
|   +-- agents/
|   |   +-- __init__.py
|   |   +-- ideator.py           # Node A: Divergent idea generation (3x10)
|   |   +-- selector.py          # Node A.5: Diversity-maximizing selection
|   |   +-- recombiner.py        # Node B: Convergent hybridization
|   |   +-- user_review.py       # Node A.5b: Interactive veto/star review
|   |   +-- gatekeeper.py        # Node C: Anti-wrapper veto (structured scoring)
|   |   +-- principles_judge.py  # Node D: AI-native principles scoring
|   |   +-- pre_ranker.py        # Node D.5: Feasibility/habit/monetization scoring
|   |   +-- dsr_designer.py      # Node E: DSR experiment protocols
|   |   +-- ranker.py            # Node F: Final aggregation + ranking
|   +-- prompts/
|       +-- ideator_system.md
|       +-- ideator_user.md
|       +-- recombiner_system.md
|       +-- recombiner_user.md
|       +-- gatekeeper_system.md
|       +-- gatekeeper_user.md
|       +-- principles_judge_system.md
|       +-- principles_judge_user.md
|       +-- pre_ranker_system.md
|       +-- pre_ranker_user.md
|       +-- dsr_designer_system.md
|       +-- dsr_designer_user.md
|       +-- angel_rescue_system.md
|       +-- angel_rescue_user.md
|       +-- ranker_system.md
|       +-- ranker_user.md
+-- outputs/
|   +-- runs/<timestamp>/
|       +-- raw_ideas.jsonl
|       +-- selected_ideas.jsonl
|       +-- hybrids.jsonl
|       +-- gate_results.jsonl
|       +-- principle_scores.jsonl
|       +-- pre_ranker_scores.jsonl
|       +-- dsr_protocols.md
|       +-- final_ranked.md
|       +-- next_7_days_plan.md
|       +-- run.log.json           # Detailed structured JSON log
|       +-- checkpoint.json        # Pipeline state for resume
+-- tests/
    +-- test_schema_validation.py
    +-- test_gatekeeper_logic.py
    +-- test_ranker_stability.py
```

---

## 5. LLM Configuration

### 5.1 Provider
All LLM calls go through **OpenRouter** (https://openrouter.ai/api/v1) using an OpenAI-compatible client.

### 5.2 Model Assignments

Config uses friendly names that map to OpenRouter slugs:

| Friendly Name | OpenRouter Slug | Used By |
|---------------|-----------------|---------|
| qwen-72b | qwen/qwen-2.5-72b-instruct | Ideator (A), Recombiner (B), Angel's Rescue (C sub-routine) |
| llama-70b | meta-llama/llama-3.1-70b-instruct | Gatekeeper (C), Principles Judge (D), Pre-Ranker (D.5), Ranker (F) |
| deepseek-r1-32b | deepseek/deepseek-r1-distill-qwen-32b | DSR Designer (E) |
| qwen-14b | qwen/qwen-2.5-14b-instruct | Schema Repair (utility fallback) |

### 5.3 Temperature Configuration

| Agent | Temperature | Rationale |
|-------|-------------|-----------|
| Ideator | 0.7-0.9 | Encourage creativity |
| Recombiner | 0.6-0.7 | Balance creativity and coherence |
| Gatekeeper | 0.2-0.3 | Consistent evaluation |
| Principles Judge | 0.2 | Consistent scoring |
| Pre-Ranker | 0.2 | Consistent scoring |
| DSR Designer | 0.2-0.3 | Structured reasoning |
| Ranker | 0.1-0.2 | Deterministic ranking |

### 5.4 Schema Repair Mechanism
On any schema validation failure from a primary agent:
1. Do NOT retry with the primary agent
2. Immediately route the malformed output + target Pydantic schema to the **qwen-14b** repair agent
3. If repair also fails, skip that individual idea and log the failure
4. Maximum 1 repair attempt per item

### 5.5 Prompt Templating
Use **LangChain PromptTemplate / ChatPromptTemplate** with `{variable}` syntax.
All prompts stored as `.md` files under `src/prompts/`.
Each agent has a system prompt and a user prompt template.

---

## 6. Pipeline Design (LangGraph Nodes)

### Overview

```
Node A: Ideator (3x10 ideas, by user segment, with optional user profile)
    |
Node A.5: Selector (diversity-maximizing, pick top_k)
    |
Node A.5b: User Review (interactive veto/star, skipped with --no-pause)
    |
    +--> top_k raw ideas --------+
    |                            |
Node B: Recombiner (min 5 hybrids)
    |                            |
    +--> hybrids                 |
         |                       |
         +--- all candidates ----+  (top_k raw + hybrids)
              |
Node C: Gatekeeper (structured 0-10 scores, programmatic thresholds)
              |--- Angel's Rescue sub-routine (on KILL, before confirming)
              |
         survivors only
              |
Node D: Principles Judge (0-2 per principle)
              |
Node D.5: Pre-Ranker (feasibility w/ user profile, habit, monetization w/ market search)
              |
Node E: DSR Designer (validation protocol per survivor)
              |
Node F: Ranker (aggregate, rank, 7-day plan)
```

### Node A: IDEATOR (Divergent)

**Purpose:** Generate diverse raw ideas

| Parameter | Value |
|-----------|-------|
| Input | domain (from config), n_raw (default 30), user_profile (optional) |
| Output | n_raw idea objects |
| LLM Calls | 3 calls of n_raw/3 ideas each |
| Model | qwen-72b |
| Temperature | 0.7-0.9 |

**Call Variation Strategy (by user segment):**
- Call 1: Solopreneurs / Freelancers
- Call 2: Corporate Knowledge Workers / Managers
- Call 3: Students / Researchers

Each call generates n_raw/3 ideas targeted at its user segment.

**Required Fields per Idea:**
- Hook loop
- AI magic moment
- User segment
- MVP scope
- One-line "AI-essential claim"

**User Context Injection:**
When a user profile is configured, the ideator system prompt includes the developer's skills, stack, and past projects. The LLM is instructed to prioritize ideas that leverage these "unfair advantages" -- e.g., a medical background enables health-AI ideas that other developers cannot credibly build.

When no profile is configured, prompts are unchanged from the generic behavior.

**Auto-Retry on Total Wipeout:**
If all ideas are later killed by the Gatekeeper, re-run the Ideator with DIFFERENT user segments:
- Retry segments: Creators / Content Producers, Team Leads / Coordinators, Consultants / Advisors
- Maximum 1 retry (configurable via max_retries in config.yaml)
- If retry also produces all kills, complete the run with a "no survivors" report

---

### Node A.5: SELECTOR (Diversity-Maximizing)

**Purpose:** Select top_k diverse ideas from n_raw using embedding-based clustering

| Parameter | Value |
|-----------|-------|
| Input | n_raw ideas |
| Output | top_k ideas (default 10) |

**Algorithm:**
1. Compute embeddings for each idea (concatenate name + hook_loop + ai_magic_moment + ai_essential_claim)
2. Cluster ideas using k-means (k = top_k)
3. Select the idea closest to each cluster centroid

**Embedding Provider:**
- Primary: OpenRouter embedding model
- Fallback: scikit-learn TF-IDF vectorization (automatic on API failure)

---

### Node A.5b: USER REVIEW (Interactive Pause)

**Purpose:** Let the user inspect selected ideas before expensive downstream processing

| Parameter | Value |
|-----------|-------|
| Input | top_k selected ideas |
| Output | Filtered ideas + starred IDs |
| CLI Flag | `--no-pause` to skip |

**Interaction:**

1. Display all selected ideas (name, hook, AI magic moment)
2. User may VETO ideas (remove from pipeline)
3. User may STAR ideas (force-include through gatekeeper -- immune to KILL)
4. Press Enter to accept current selection unchanged

**Non-Interactive Mode:** When `--no-pause` is passed, this node is a passthrough.

**Starred Ideas:** Starred ideas go through gatekeeper scoring (for data collection) but cannot be killed. Angel's Rescue is not triggered for starred ideas since they are already protected.

---

### Node B: RECOMBINER (Convergent)

**Purpose:** Combine and enhance top ideas into hybrids

| Parameter | Value |
|-----------|-------|
| Input | top_k selected ideas |
| Output | Minimum 5 hybrids (no upper bound) |
| Model | qwen-72b |
| Temperature | 0.6-0.7 |

**Requirements:**
- Each hybrid must add a compounding advantage
- Compounding mechanisms: memory, data loop, workflow embedding
- Must explicitly state "compounding advantage mechanism"

**Validation:** Schema requires minimum 5 hybrids. If fewer, retry once with a prompt emphasizing "combine pairs and triples of the input ideas".

---

### Node C: ANTI-WRAPPER GATEKEEPER (Hard Veto)

**Purpose:** Filter out wrapper ideas using structured scoring and programmatic thresholds

| Parameter | Value |
|-----------|-------|
| Input | top_k raw ideas + hybrids (all candidates) |
| Output | Pass list + Kill list |
| Model | llama-70b |
| Temperature | 0.2-0.3 |
| Calls | 1 per idea (individual evaluation) |

**Evaluation (LLM outputs structured JSON per idea):**

| Question | LLM Output | Score Range |
|----------|------------|-------------|
| Q1: Can generic ChatGPT prompts achieve 80% of value? | wrapper_risk_score (0-10, higher = more wrapper-like) + reasoning | 0-10 |
| Q2: Workflow embedding strength | embedding_score (0-10, higher = stronger embedding) + where it embeds | 0-10 |
| Q3: Compounding advantage strength | compounding_score (0-10, higher = stronger moat) + what improves + why hard to copy | 0-10 |

**Programmatic Kill Thresholds (strict, configurable in config.yaml):**
- Q1 wrapper_risk_score >= 6 --> KILL (too much overlap with generic ChatGPT)
- Q2 embedding_score <= 3 --> KILL (weak workflow integration)
- Q3 compounding_score <= 3 --> KILL (no real moat)
- If ANY threshold triggers --> status = KILL with reason

**Angel's Rescue Sub-Routine:**

Before confirming a KILL, the gatekeeper triggers an Angel's Advocate agent:

| Parameter | Value |
|-----------|-------|
| Model | qwen-72b |
| Temperature | 0.7 |
| Trigger | Any idea that fails kill thresholds |
| Attempts | Maximum 1 per idea (no recursion) |

**Logic:**

1. Idea fails threshold check -- status would be KILL
2. If idea is starred by user -- skip rescue, force PASS
3. Otherwise -- send to Angel's Advocate with kill reasons + scores
4. Angel asks: "Can this idea be saved by adding ONE specific feature that creates a data moat?"
5. If verdict = "save": rewrite idea fields (name, hook_loop, ai_magic_moment, mvp_scope, ai_essential_claim, compounding_advantage) and re-score through gatekeeper
6. If verdict = "kill": confirm original KILL
7. If re-scored idea still fails thresholds: confirm KILL (no second rescue)

**Output Extension:**
GateResult gains two fields:

- `rescued: bool` -- True if angel's rescue saved this idea
- `rescue_pivot: str | None` -- The specific data-moat feature that saved it

---

### Node D: AI-NATIVE PRINCIPLES JUDGE (Scoring)

**Purpose:** Score survivors on 5 AI-native design principles

| Parameter | Value |
|-----------|-------|
| Input | Surviving ideas (passed gate) |
| Output | Per-idea score breakdown |
| Model | llama-70b |
| Temperature | 0.2 |
| Scale | 0-2 per principle |
| Calls | 1 per idea |

**Principles:**

| # | Principle | Description |
|---|-----------|-------------|
| 1 | Adaptive trust calibration | System adjusts based on user trust level |
| 2 | Sandwich workflow | Human-AI-Human collaboration pattern |
| 3 | Contextual continuity | Memory across time/tasks |
| 4 | Outcome-aligned monetization | Pricing aligned to user outcomes |
| 5 | Progressive disclosure / GenUI | Reduces complexity over time |

**Output:**
- Per-idea score breakdown (total 0-10)
- 1 concrete design change to raise weakest dimension

---

### Node D.5: PRE-RANKER (Feasibility/Habit/Monetization Scoring)

**Purpose:** Score survivors on execution-relevant dimensions

| Parameter | Value |
|-----------|-------|
| Input | Surviving ideas (passed gate) |
| Output | Per-idea score breakdown |
| Model | llama-70b |
| Temperature | 0.2 |
| Scale | 0-2 per dimension |
| Calls | 1 per idea (all 3 dimensions in one call) |

**Dimensions:**

| # | Dimension | Criteria |
|---|-----------|----------|
| 1 | Feasibility | Can a solo dev build an MVP in 4 weeks? Does the user's listed stack support this? Does it require domain expertise the user doesn't list? |
| 2 | Habit potential | Will users return repeatedly? Is there a natural usage cadence? |
| 3 | Monetization plausibility | Is there evidence of market demand? Is there a clear willingness-to-pay signal? |

**User Profile in Feasibility:**
When a user profile is configured, the feasibility rubric explicitly checks:

- Does the user's tech stack (e.g., Python/LangGraph) support this idea?
- Does the idea require domain expertise the user does not list?
- Score higher when the idea aligns with existing skills; lower when it requires unfamiliar technologies.

When no profile is configured, feasibility uses the generic "solo dev, 4 weeks" criteria.

**Market Evidence Search (Fact-Check Tool):**

Before the LLM scores monetization, the pre-ranker queries a search engine for demand signals.

| Parameter | Value |
|-----------|-------|
| Provider | DuckDuckGo (free, no API key) |
| Query | `"{idea_name} {user_segment} app competitor"` |
| Max Results | 3 |
| Timeout | 10 seconds |

**Logic:**

1. Search for competitors or relevant keywords
2. Pass search results into the LLM prompt as context
3. If search finds zero evidence of demand, the LLM is instructed to lower the monetization score
4. If search fails or times out, fall back to LLM-only scoring (graceful degradation)

**Output Extension:**
PreRankerScore gains: `market_evidence: str | None` -- summary of search results used in scoring.

---

### Node E: DSR EXPERIMENT DESIGNER (Validation Protocol)

**Purpose:** Create a validation protocol for each survivor

| Parameter | Value |
|-----------|-------|
| Input | Surviving ideas with all scores |
| Output | 1-page protocol per idea in Markdown |
| Model | deepseek-r1-32b |
| Temperature | 0.2-0.3 |
| Calls | 1 per idea |

**Protocol Components:**
1. **Problem framing** + assumptions list
2. **Wizard-of-Oz test plan** (3 steps)
3. **Hook metrics:** activation, repeated meaningful use, reliance ratio
4. **$1 reservation test (structured WTP assessment):**
   - What the $1 offer would be
   - Target buyer persona
   - Headline and value proposition framing
   - Predicted conversion drivers and objections
5. **Trust-breaker checklist** (top 3 likely failures)
6. **Falsification criteria** (how to kill within 7 days)

---

### Node F: RANKER + RECOMMENDER

**Purpose:** Aggregate all scores and produce final recommendations

| Parameter | Value |
|-----------|-------|
| Input | All scored survivors |
| Output | Ranked list + 7-day plan |
| Model | llama-70b |
| Temperature | 0.1-0.2 |

**Aggregation (fixed equal weights):**

| Factor | Source | Weight |
|--------|--------|--------|
| Gatekeeper status | Node C | Required PASS (filter, not scored) |
| Principles score (0-10) | Node D | Equal |
| Feasibility score (0-2) | Node D.5 | Equal |
| Habit score (0-2) | Node D.5 | Equal |
| Monetization score (0-2) | Node D.5 | Equal |

All scores are normalized to 0-1 before summation. Final score = sum of normalized scores.

**Output:**
- Ranked list of all survivors (could be fewer than 5)
- 1-paragraph rationale per idea
- If fewer than 5 survive, report notes why
- `next_7_days_plan.md` for #1 idea

**7-Day Plan Structure:**

| Days | Activities |
|------|------------|
| Day 1-2 | Landing page + interview script + WOZ setup |
| Day 3-4 | Recruit testers + run tests |
| Day 5 | Analyze results + decision |
| Day 6-7 | Build MVP thin slice or pivot |

---

## 7. Data Models (Pydantic Schemas)

### 7.1 IdeaCandidate
```python
class IdeaCandidate(BaseModel):
    id: str
    name: str
    hook_loop: str
    ai_magic_moment: str
    user_segment: str
    mvp_scope: str
    ai_essential_claim: str
    domain: str
    source: Literal["raw", "hybrid"]
    compounding_advantage: Optional[str] = None
```

### 7.2 GateResult
```python
class GateResult(BaseModel):
    idea_id: str
    q1_wrapper_risk_score: int        # 0-10
    q1_reason: str
    q2_embedding_score: int           # 0-10
    q2_workflow_embedding: str
    q3_compounding_score: int         # 0-10
    q3_hard_to_copy_reason: str
    status: Literal["PASS", "KILL"]
    kill_reason: Optional[str] = None
    rescued: bool = False
    rescue_pivot: Optional[str] = None
```

### 7.2a AngelRescueResult

```python
class AngelRescueResult(BaseModel):
    verdict: Literal["save", "kill"]
    pivot_feature: str
    rewritten_name: Optional[str] = None
    rewritten_hook_loop: Optional[str] = None
    rewritten_ai_magic_moment: Optional[str] = None
    rewritten_mvp_scope: Optional[str] = None
    rewritten_ai_essential_claim: Optional[str] = None
    rewritten_compounding_advantage: Optional[str] = None
    rescue_rationale: str
```

### 7.3 PrincipleScore
```python
class PrincipleScore(BaseModel):
    idea_id: str
    adaptive_trust: int       # 0-2
    sandwich_workflow: int    # 0-2
    contextual_continuity: int  # 0-2
    outcome_monetization: int   # 0-2
    progressive_disclosure: int  # 0-2
    total_score: int            # 0-10
    weakest_dimension: str
    improvement_suggestion: str
```

### 7.4 PreRankerScore
```python
class PreRankerScore(BaseModel):
    idea_id: str
    feasibility: int          # 0-2
    habit_potential: int      # 0-2
    monetization: int         # 0-2
    total_score: int          # 0-6
    feasibility_rationale: str
    habit_rationale: str
    monetization_rationale: str
    market_evidence: Optional[str] = None
```

### 7.5 DSRProtocol
```python
class ReservationTest(BaseModel):
    offer_description: str
    target_persona: str
    headline: str
    value_proposition: str
    conversion_drivers: List[str]
    anticipated_objections: List[str]

class DSRProtocol(BaseModel):
    idea_id: str
    problem_framing: str
    assumptions: List[str]
    woz_test_steps: List[str]         # 3 steps
    hook_metrics: Dict[str, str]      # activation, repeated_use, reliance_ratio
    reservation_test: ReservationTest
    trust_breakers: List[str]         # Top 3
    falsification_criteria: str
```

### 7.6 FinalRanking
```python
class FinalRanking(BaseModel):
    rank: int
    idea_id: str
    idea_name: str
    total_score: float
    rationale: str
    gate_status: Literal["PASS"]
    principle_score: int        # 0-10
    feasibility_score: int      # 0-2
    habit_score: int            # 0-2
    monetization_score: int     # 0-2
```

### 7.7 UserProfile

```python
class UserProfile(BaseModel):
    skills: List[str] = []
    stack: List[str] = []
    past_projects: List[str] = []
```

### 7.8 SearchConfig

```python
class SearchConfig(BaseModel):
    enabled: bool = False
    provider: str = "duckduckgo"
    max_results: int = 3
    timeout_seconds: int = 10
```

---

## 8. LangGraph Implementation

### 8.1 State Definition
```python
class PipelineState(TypedDict):
    config: PipelineConfig
    raw_ideas: List[IdeaCandidate]
    selected_ideas: List[IdeaCandidate]
    hybrids: List[IdeaCandidate]
    all_candidates: List[IdeaCandidate]   # selected + hybrids
    gate_results: List[GateResult]
    survivors: List[IdeaCandidate]
    principle_scores: List[PrincipleScore]
    pre_ranker_scores: List[PreRankerScore]
    dsr_protocols: List[DSRProtocol]
    final_ranking: List[FinalRanking]
    retry_count: int
    starred_ids: List[str]          # Ideas starred by user (force-included)
    interactive: bool               # Whether to pause for user review
```

### 8.2 Checkpointing
- After each node completes, persist full PipelineState as `checkpoint.json`
- CLI supports `--resume <run_id>` to pick up from the last completed node
- Checkpoint includes: last_completed_node, full state, timestamp

### 8.3 Storage
- File-based OutputStore
- JSONL for data artifacts, Markdown for reports
- Intermediate files written progressively (raw_ideas.jsonl as soon as Node A finishes, etc.)

### 8.4 CLI Interface
```bash
# Run pipeline
python -m src.main run --n_raw 30 --top_k 10 --seed 42 --domain productivity

# Run pipeline without interactive review pause
python -m src.main run --n_raw 30 --top_k 10 --seed 42 --no-pause

# Resume a failed run
python -m src.main run --resume <run_id>

# Inspect a past run
python -m src.main inspect <run_id>

# Validate config and test connectivity
python -m src.main config-check
```

### 8.5 Logging
- **Console:** Concise progress summary (node name, idea counts, pass/kill stats)
- **File:** Detailed structured JSON log saved as `run.log.json` per run
  - Events: node_start, node_end, llm_call, schema_validation, schema_repair, kill, pass
  - Each event includes: timestamp, node, event_type, details

---

## 9. Configuration (config.yaml)

```yaml
# LLM Provider
openrouter:
  api_key_env: "OPENROUTER_API_KEY"    # reads from env var
  base_url: "https://openrouter.ai/api/v1"

# Model mapping (friendly name -> OpenRouter slug)
models:
  qwen-72b: "qwen/qwen-2.5-72b-instruct"
  llama-70b: "meta-llama/llama-3.1-70b-instruct"
  deepseek-r1-32b: "deepseek/deepseek-r1-distill-qwen-32b"
  qwen-14b: "qwen/qwen-2.5-14b-instruct"

# Agent -> model assignment
agents:
  ideator:
    model: qwen-72b
    temperature: 0.8
  recombiner:
    model: qwen-72b
    temperature: 0.65
  gatekeeper:
    model: llama-70b
    temperature: 0.25
  principles_judge:
    model: llama-70b
    temperature: 0.2
  pre_ranker:
    model: llama-70b
    temperature: 0.2
  dsr_designer:
    model: deepseek-r1-32b
    temperature: 0.25
  ranker:
    model: llama-70b
    temperature: 0.15
  schema_repair:
    model: qwen-14b
    temperature: 0.0
  angel_rescue:
    model: qwen-72b
    temperature: 0.7

# Embedding (for diversity selection)
embedding:
  provider: openrouter         # "openrouter" or "tfidf"
  model: "openai/text-embedding-3-small"   # OpenRouter embedding model
  fallback: tfidf              # automatic fallback on API failure

# Gatekeeper thresholds (strict)
gatekeeper:
  q1_kill_threshold: 6         # wrapper_risk >= 6 -> KILL
  q2_kill_threshold: 3         # embedding_score <= 3 -> KILL
  q3_kill_threshold: 3         # compounding_score <= 3 -> KILL

# Pipeline defaults
pipeline:
  domain: productivity
  n_raw: 30
  top_k: 10
  min_hybrids: 5
  max_retries: 1
  seed: 42

# User profile (optional -- pipeline works without it)
user_profile:
  skills: ["Python", "LangGraph", "FastAPI", "medical background"]
  stack: ["Python", "LangGraph", "OpenRouter", "Pydantic"]
  past_projects: ["AI diagnosis assistant", "clinical note summarizer"]

# Market search for pre-ranker monetization scoring
search:
  enabled: true
  provider: duckduckgo
  max_results: 3
  timeout_seconds: 10

# Output
output:
  dir: "./outputs"
```

---

## 10. Failure Handling

### 10.1 Schema Failures
1. Primary agent returns malformed JSON
2. Immediately route to qwen-14b repair agent (no retry with primary)
3. If repair also fails, skip that individual idea, log the failure
4. Maximum 1 repair attempt per item

### 10.2 Total Gatekeeper Wipeout
1. If all candidates are killed, trigger auto-retry
2. Re-run Ideator with different user segment variations:
   - Retry segments: Creators/Content Producers, Team Leads/Coordinators, Consultants/Advisors
3. Maximum 1 retry (configurable)
4. If retry also produces all kills, complete the run with a "no survivors" report

### 10.3 Low Survivor Count
- If fewer than 5 ideas survive, rank whatever survives
- Report notes the low count and summarizes common kill reasons
- 7-day plan still generated for #1 (if any survivors exist)

### 10.4 Mid-Pipeline Failures
- Checkpoint after each node
- CLI `--resume <run_id>` picks up from last completed node
- Intermediate output files are written progressively

---

## 11. Testing Requirements

**All tests are integration tests requiring a valid OpenRouter API key.**

### 11.1 test_schema_validation.py
- Send real LLM calls through each agent
- Validate all Pydantic models parse correctly from actual LLM output
- Test the schema repair fallback with intentionally malformed responses

### 11.2 test_gatekeeper_logic.py
- Run the gatekeeper on a known set of ideas (some obvious wrappers, some strong)
- Verify PASS/KILL outcomes align with threshold logic
- Test threshold edge cases

### 11.3 test_ranker_stability.py
- Run the full pipeline twice with same seed
- Verify ranking order is consistent (best-effort, may differ due to LLM non-determinism)
- Test equal-weight aggregation math with known score inputs

---

## 12. Output Artifacts

### 12.1 Per-Run Outputs
Located in `outputs/runs/<timestamp>/`:

| File | Format | Content |
|------|--------|---------|
| raw_ideas.jsonl | JSONL | All raw idea candidates |
| selected_ideas.jsonl | JSONL | Diversity-selected top_k ideas |
| hybrids.jsonl | JSONL | Recombined hybrid ideas |
| gate_results.jsonl | JSONL | Pass/kill results with structured scores |
| principle_scores.jsonl | JSONL | 5-principle scoring per survivor |
| pre_ranker_scores.jsonl | JSONL | Feasibility/habit/monetization per survivor |
| dsr_protocols.md | Markdown | Validation protocols (survivors only) |
| final_ranked.md | Markdown | Ranked survivors with rationales (survivors only) |
| next_7_days_plan.md | Markdown | Execution plan for #1 idea |
| run.log.json | JSON | Detailed structured event log |
| checkpoint.json | JSON | Pipeline state for resume |

**Report scope:** Markdown reports contain survivors only. Killed ideas and reasons are in gate_results.jsonl only.

---

## 13. Success Criteria

1. **Functional:** CLI produces all output artifacts without errors
2. **Reproducible:** Same seed produces best-effort similar outputs (logged for traceability)
3. **Validated:** All outputs pass Pydantic schema validation
4. **Documented:** README enables new user to run in <5 minutes
5. **Tested:** All integration tests pass with a valid API key
6. **Resilient:** Schema repair, auto-retry, and checkpointing handle common failure modes
7. **Multi-Domain:** Pipeline works for domains beyond productivity when configured

---

## Appendix A: Environment Variables

```bash
OPENROUTER_API_KEY=your-openrouter-api-key
LOG_LEVEL=INFO                              # optional, default INFO
```

All other configuration lives in config.yaml.

---

## Appendix B: Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd <repo>
pip install -e .

# 2. Set environment
export OPENROUTER_API_KEY=your-key

# 3. Validate config
python -m src.main config-check

# 4. Run pipeline
python -m src.main run --n_raw 30 --top_k 10 --seed 42

# 5. Check outputs
python -m src.main inspect <run_id>

# 6. Or browse directly
ls outputs/runs/
```

---

## Appendix C: Interview Decisions Log

Decisions made during the 8-round design interview (v2.0):

| # | Decision | Choice |
|---|----------|--------|
| 1 | LLM Provider | OpenRouter (OpenAI-compatible API) |
| 2 | Reproducibility | Best-effort seeding |
| 3 | Top-k selection heuristic | Diversity-maximizing (embedding clustering) |
| 4 | Ranker score source | New pre-Ranker scoring node (D.5) |
| 5 | Embedding approach | OpenRouter embedding model, TF-IDF fallback |
| 6 | Gatekeeper logic | Structured 0-10 scores + programmatic thresholds |
| 7 | Ranking weights | Fixed equal weights |
| 8 | Failure handling | Auto-retry with backoff |
| 9 | Gate scope | Both raw top-10 and hybrids (18 candidates) |
| 10 | Schema repair | Immediate fallback to qwen-14b utility agent |
| 11 | Reservation test | Structured WTP assessment |
| 12 | Hybrid count | Unconstrained with minimum 5 |
| 13 | Ranker model | Llama-3.1-70B (same as Judge) |
| 14 | Batch strategy | Individual calls (1 per idea) |
| 15 | Idea generation | Multiple calls (10 per call, 3 calls) |
| 16 | Prompt templating | LangChain PromptTemplate |
| 17 | Parallelism | Sequential (safe, simple) |
| 18 | Ideator variation | By user segment |
| 19 | Configuration | Single config.yaml file |
| 20 | Logging | Console summary + detailed JSON log |
| 21 | Kill thresholds | Strict (Q1>=6, Q2<=3, Q3<=3) |
| 22 | Pre-Ranker scale | 0-2 (matching Principles Judge) |
| 23 | Retry strategy | Different user segments |
| 24 | Report scope | Survivors only |
| 25 | Model config | Friendly names with mapping |
| 26 | Test strategy | Integration tests only |
| 27 | CLI scope | run + inspect + config-check |
| 28 | FOR_YELLOW.md | Skip for now |
| 29 | Checkpointing | Yes, between nodes with --resume |
| 30 | Low survivors | Return whatever survives |
| 31 | Embedding fallback | TF-IDF on API failure |
| 32 | Domain scope | Multi-domain support (parameterized prompts) |
| 33 | Angel's Rescue | Sub-routine in gatekeeper before kill confirmation (qwen-72b) |
| 34 | User Profile | Optional config section injected into ideator + pre-ranker |
| 35 | CLI Pause | Interactive review after selector, --no-pause to skip |
| 36 | Market Search | DuckDuckGo for monetization evidence, graceful fallback |
| 37 | Starred Ideas | User-starred ideas bypass gatekeeper kill |

---

*End of Specification Document v3.0*
