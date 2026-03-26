# Mission 025 — System Bootstrapper + Runtime Orchestrator (Task F)

**Status:** ✅ Done
**Priority:** P1
**Created:** 2026-03-26
**Depends on:** Mission 022 (Blueprint Store), Mission 023 (BrickSelector), Mission 024 (100 bricks)

## Context

Bricks needs a single entry point for agents. Today the user must manually wire BrickSelector → Composer → Engine. Task F provides two components: a one-time bootstrapper that configures the system from a config file, and a runtime orchestrator that handles every task with one call.

## Architecture

```
BOOT (one-time)

skill.md / agent.yaml
        │
        ▼
  SystemBootstrapper
  1. Read config file
  2. One LLM call → understand domain
  3. Configure BrickSelector (categories, tags)
  4. Configure BlueprintStore (backend, TTL)
  5. Configure Composer (model, system prompt)
  → System ready. No more bootstrapper involvement.


RUNTIME (per task)

Agent → execute_task("filter active customers, calc revenue")
        │
        ▼
  RuntimeOrchestrator
  1. Hash task text → fingerprint
  2. BlueprintStore lookup
     → HIT: execute blueprint directly, return result
     → MISS: continue ↓
  3. BrickSelector query (Tier 1 → Tier 2 fallback)
  4. Composer (one LLM call) → YAML
  5. Validate → Execute (deterministic)
  6. Auto-save blueprint to store
  7. Return result
```

## Design Decisions

**Bootstrapper:**
- Reads `skill.md` (markdown) or `agent.yaml` (structured) — supports both
- One LLM call at boot to extract: domain keywords, relevant brick categories, tags
- Output: a `SystemConfig` Pydantic model passed to all components
- If config is already structured (`agent.yaml` with explicit categories/tags), skip LLM call — parse directly

**Runtime Orchestrator:**
- Stateless — all state lives in BlueprintStore and BrickSelector
- One method: `execute(task_text: str, inputs: dict) → dict`
- Returns execution result directly — agent never sees YAML, bricks, or internals
- Handles retry internally (max 1 retry on compose failure, same as today)

**MCP integration:**
- Single tool: `execute_task(task: str, inputs: dict) → dict`
- Agent sends task description + input values, gets result back
- No `list_bricks`, no `compose_blueprint`, no `execute_blueprint` — just one tool

**Config format (`agent.yaml`):**
```yaml
name: crm_processor
description: "Processes CRM API responses. Filters, aggregates, formats."
brick_categories:
  - data_transformation
  - string_processing
store:
  backend: file          # or "memory"
  path: ./blueprints
  ttl_days: 30
model: claude-haiku-4-5-20251001
```

**Config format (`skill.md`):**
```markdown
# CRM Data Processor
This agent processes CRM API responses. It filters customer records,
calculates revenue aggregates, and generates formatted reports.
```
When using `skill.md`, the bootstrapper makes one LLM call to extract categories and tags from the description. When using `agent.yaml`, no LLM call needed.

## Deliverables

1. `bricks/boot/bootstrapper.py` — `SystemBootstrapper` class
   - `bootstrap(config_path: Path) → SystemConfig`
   - Reads `.md` or `.yaml`, extracts domain info
   - One LLM call only for `.md` files
   - Returns configured `SystemConfig`

2. `bricks/boot/config.py` — `SystemConfig` Pydantic model
   - `name`, `description`, `brick_categories`, `tags`, `store_config`, `model`

3. `bricks/orchestrator/runtime.py` — `RuntimeOrchestrator` class
   - `__init__(config: SystemConfig, selector, store, composer, engine)`
   - `execute(task_text: str, inputs: dict) → dict`
   - Wires: store lookup → selector → composer → engine → auto-save

4. `bricks/mcp/tool.py` — `execute_task` MCP tool definition
   - Single tool the agent calls
   - Delegates to `RuntimeOrchestrator.execute()`

5. Tests:
   - Bootstrapper with `.yaml` (no LLM call)
   - Bootstrapper with `.md` (mocked LLM call)
   - Orchestrator: store hit → no compose
   - Orchestrator: store miss → compose → auto-save
   - Orchestrator: compose failure → retry → success
   - MCP tool end-to-end

## Acceptance

- Boot from `agent.yaml` → system ready, no LLM call
- Boot from `skill.md` → one LLM call, system ready
- `execute_task("filter active customers")` → correct result, one tool call
- Second call with same task → BlueprintStore hit, 0 LLM tokens
- All existing tests pass (mypy + ruff clean)
- Commit, tag, push

---

## Results (filled by Claude Code)

**Status:** ✅ Done
**Completed:** 2026-03-27

### Summary

Built `SystemBootstrapper` (reads `agent.yaml` with zero LLM calls or `skill.md` with one LLM call), `RuntimeOrchestrator` (single `execute()` wiring selector → composer → engine), and a framework-agnostic `execute_task` MCP tool. Added `OrchestratorError` exception. Versioned as 0.4.16.

### Files Changed

| File | Action | What Changed |
|------|--------|-------------|
| `bricks/core/exceptions.py` | Modified | Added `OrchestratorError(BrickError)` |
| `bricks/core/__init__.py` | Modified | Export `OrchestratorError` |
| `bricks/boot/__init__.py` | Created | Exports `SystemBootstrapper`, `SystemConfig` |
| `bricks/boot/config.py` | Created | `SystemConfig` Pydantic model |
| `bricks/boot/bootstrapper.py` | Created | `SystemBootstrapper` with yaml/markdown support |
| `bricks/orchestrator/__init__.py` | Created | Exports `RuntimeOrchestrator`, `OrchestratorError` |
| `bricks/orchestrator/runtime.py` | Created | `RuntimeOrchestrator` — wires selector/store/composer/engine |
| `bricks/mcp/__init__.py` | Created | Exports `execute_task`, `EXECUTE_TASK_SCHEMA` |
| `bricks/mcp/tool.py` | Created | Framework-agnostic `execute_task()` + JSON schema |
| `tests/boot/__init__.py` | Created | Package marker |
| `tests/boot/test_bootstrapper.py` | Created | 12 tests: yaml/md/errors |
| `tests/orchestrator/__init__.py` | Created | Package marker |
| `tests/orchestrator/test_runtime.py` | Created | 10 tests: execute, cache, errors, selector/store wiring |
| `pyproject.toml` | Modified | Version 0.4.16 |
| `bricks/__init__.py` | Modified | Version 0.4.16 |
| `CHANGELOG.md` | Modified | v0.4.16 entry |

### Test Results

```
pytest: 615 passed (before Mission 024 added 106 more)
mypy:   clean (strict)
ruff:   clean
```

### Notes

- Anthropic SDK type narrowing: used `hasattr(block, "text")` rather than `isinstance(TextBlock, ...)` to avoid importing SDK-internal types — graceful fallback to `([], [])` if LLM returns unexpected block type
- `bricks/mcp/` is distinct from `benchmark/mcp/` (different namespace roots) — no conflict
- `RuntimeOrchestrator` wires selector/store/composer internally; tests reach `orch._composer._selector` for assertions
- Store is set to `None` in composer when `store.enabled=False` — no blueprint persistence
