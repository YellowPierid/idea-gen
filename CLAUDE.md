# CLAUDE.md - System Instructions & Engineering Standards

Behavioral guidelines for AI-assisted development. These reduce common LLM mistakes and enforce project standards.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

---

## 1. Output Format Standards

**ASCII-only. No emojis. No visual noise.**

- **NO EMOJIS**: Never use emojis (❌, ✅, 🚀, etc.) in code, comments, logs, or messages.
- **Text-based indicators**: Use standard log levels instead:
  - `[ERROR]` or `[FAIL]` instead of ❌
  - `[SUCCESS]` or `[OK]` instead of ✅
  - `[WARN]` instead of ⚠️
  - `[INFO]` instead of ℹ️ or 🚀
- **ASCII-safe**: All source code and output must be strictly ASCII-compatible.
- **Logging**: Plain text only. No ANSI color codes unless explicitly requested.

---

## 2. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
1. **State assumptions explicitly** - If uncertain, ask clarifying questions.
2. **Present multiple interpretations** - Don't pick silently when alternatives exist.
3. **Suggest simpler approaches** - Push back when warranted. Question the requirements if they seem overcomplicated.
4. **Stop when unclear** - Name what's confusing. Get clarity before proceeding.

For complex tasks, sketch the approach first:
```
Analysis: [What problem are we really solving?]
Plan: [High-level steps]
Tradeoffs: [What are we optimizing for?]
```

---

## 3. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

**The test:** "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**Prefer:**
- Pure functions and immutability where natural
- Descriptive variable names (avoid single-letter except standard iterators)
- Comments that explain "why," not "what"
- Robust try/catch blocks with clear, text-based error context

---

## 4. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the user's request.

---

## 5. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform vague tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan with verification points:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria enable independent iteration. Weak criteria ("make it work") require constant clarification.

---

## 6. Token & Tool Usage Guardrails (Claude Code / MCP)

Claude Code usage is constrained by context size and tool-call volume. Follow these rules to minimize tokens and avoid quota exhaustion.

### 6.1 Default posture: "narrow scope, no exploration"
- Do not scan the repository. Only inspect files and folders explicitly requested or clearly required by the current plan.
- Do not call tools before producing a short plan (5-10 lines) that lists the exact files/folders to touch.
- Keep the working set small: prefer modifying 1-3 files per iteration.

### 6.2 Hard limits per iteration
- Tool calls: maximum 2 per iteration (plan -> 1-2 tool calls -> synthesize -> patch).
- Directory listing: non-recursive by default. Recurse only into a single target subfolder when explicitly required.
- File reads: read the minimum necessary excerpt (top-of-file + relevant functions). Avoid full-file reads unless the file is small.

### 6.3 Explicit exclusions (never enumerate or read unless asked)
- `node_modules/`, `.git/`, `dist/`, `build/`, `out/`, `coverage/`
- `venv/`, `.venv/`, `__pycache__/`, `.pytest_cache/`
- `data/`, `datasets/`, `outputs/`, `logs/`, `tmp/`, `cache/`

### 6.4 Patch discipline to reduce repeated context
- Prefer unified diffs over reprinting whole files.
- Avoid repeated rewrites of the same file. Make one focused change, then run one verification step.
- Defer refactors until after the feature works and tests pass.

### 6.5 Memory and handoff hygiene
- Maintain a short, human-written status file (e.g., `HANDOFF.md` or `STATUS.md`) with:
  - goal, current state, next steps, constraints, and the 3-5 key files.
- When resuming work, read the status file first; do not "rediscover" the repo.

### 6.6 When tools are permitted
- Use `list_dir` only to confirm structure for the scoped folder.
- Use search/grep only within the scoped folder and only with a narrowly targeted pattern.
- If uncertainty is high, ask one clarifying question instead of broad exploration.

---

## 7. Terminal & Tooling

**Safe, standard, portable commands.**

- **Shell commands**: Ensure bash/CLI commands are safe and cross-platform compatible where possible.
- **Git commits**: Write clear, imperative messages (e.g., "Add user authentication middleware" not "Added auth").
- **Dependencies**: Verify tool availability before use. Suggest installation if missing.

---

## 8. Hard Constraints (MUST FOLLOW)

### 8.1 NO LLM COST/TOKEN ACCOUNTING FEATURES
Do not create, re-create, or suggest any code for:
- token counting, token estimation, prompt tokenization
- cost calculation, billing estimation, price tables
- "usage tracker", "cost dashboard", "cost middleware"
- telemetry/analytics for token usage
- adapters for OpenAI/Anthropic pricing or model cost constants

If asked to add "cost" or "token" tracking, respond: **"Not in scope for this project."**

If any existing cost/token-related files are found, they should be deleted and NOT replaced.

### 8.2 Scope Definition
This project focuses on: <solving biology olympiad question>
Out of scope: token/cost tracking, billing dashboards, usage metering.

---

## 9. Be a Teacher

For every project, **write a detailed FOR_YELLOW.md file** that explains the whole project in plain language.

Include:
- The technical architecture
- The structure of the codebase and how the various parts are connected
- The technologies used and why we made these technical decisions
- Lessons learned (bugs encountered and how they were fixed, potential pitfalls, new technologies used, best practices, how good engineers think and work)

Make it engaging to read - not boring technical documentation. Use analogies and anecdotes where appropriate to make it understandable and memorable.

---

## Success Indicators

These guidelines are working if you see:
- Fewer unnecessary changes in diffs
- Fewer rewrites due to overcomplication
- Clarifying questions come before implementation, not after mistakes
- ASCII-clean output with no emoji decoration
- Code that solves the exact problem, nothing more
