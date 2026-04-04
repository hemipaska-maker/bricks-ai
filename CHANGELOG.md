# Changelog

All notable changes to the Bricks project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.38] — 2026-04-01

### Changed
- **Standardize stdlib return keys**: all stdlib bricks now return `{"result": <value>}` consistently
  - `extract_json_from_str`: `{"data": ...}` → `{"result": ...}`
  - `validate_json_schema`: `{"valid": ...}` → `{"result": ...}`
  - `extract_dict_field`: `{"value": ...}` → `{"result": ...}`
  - `count_words_chars`: `{"words": ..., "chars": ...}` → `{"result": {"words": ..., "chars": ...}}`
  - `extract_date_parts`: `{"year": ..., ...}` → `{"result": {"year": ..., ...}}`
- Updated blueprint YAML examples (`crm_pipeline`, `crm_hallucination`, `crm_reuse`): `${parsed.data}` → `${parsed.result}`

## [0.4.37] — 2026-04-04

### Added
- `bricks check-env` CLI command: diagnoses Python version, litellm install, and Windows MAX_PATH limits
- README: Windows Setup section with workaround for 260-char path limit

## [0.4.36] — 2026-04-01

### Changed
- **PyPI readiness**: renamed packages `bricks` → `bricks-ai` and `bricks-stdlib` → `bricks-ai-stdlib`
- Updated author email, URLs (GitLab → GitHub), keywords, and classifiers in both `pyproject.toml` files
- Added `[project.readme]` to both packages; created `README.md` for `packages/core/` and `packages/stdlib/`
- Both wheels build cleanly and pass `twine check`

## [0.4.35] — 2026-04-01

### Changed
- **Test structure aligned to monorepo**: all root `tests/` content moved into owning packages
  - `tests/{core,ai,boot,cli,mcp,llm,orchestrator,selector,store,integration,live}/` + `conftest.py` + top-level tests → `packages/core/tests/`
  - `tests/stdlib/` → `packages/stdlib/tests/`
- **`pyproject.toml`**: updated `testpaths` to `packages/core/tests`, `packages/stdlib/tests`, `packages/benchmark/...`; added `--import-mode=importlib` to handle same-named modules across packages
- Root `tests/` directory removed

## [0.4.34] — 2026-03-31

### Removed
- **`MY-WORKFLOW.md`**: outdated workflow doc (referenced GitLab, superseded by README/CLAUDE.md)
- **19 benchmark result directories**: all historical runs removed; 3 representative runs kept (v0.1.1, v0.4.12, v0.4.26)
- **`results.json`, `summary.md`, `determinism_report.md`**: legacy top-level result files removed from results/

### Changed
- **`.gitignore`**: added `.claude/` (local tooling config) and `showcase/results/` (generated data)
- **`.claude/settings.local.json`**: untracked (file kept locally, no longer in git)

## [0.4.33] — 2026-03-31

### Changed
- **Default branch renamed**: `development` → `main`; remote `development` deleted; GitHub default branch updated

### Added
- **GitHub Releases**: created for v0.4.25, v0.4.26, v0.4.27, v0.4.28, v0.4.32 with CHANGELOG-based notes

## [0.4.32] — 2026-03-31

### Added
- **LICENSE**: MIT license file (copyright Nahum Paska)
- **CONTRIBUTING.md**: setup instructions, code style, PR process
- **SECURITY.md**: responsible disclosure policy
- **`.github/ISSUE_TEMPLATE/bug_report.md`** and **`feature_request.md`**: structured issue templates
- **`.github/PULL_REQUEST_TEMPLATE.md`**: checklist PR template

### Fixed
- **CI workflow**: updated to monorepo install (`packages/core[dev,ai]`, `packages/stdlib`, `packages/benchmark`) replacing broken root `pip install -e ".[dev,ai,benchmark]"` — badge now green
- **CI mypy path**: `mypy packages/core/src/bricks --strict` (was `mypy bricks --strict`)
- **ruff format**: auto-formatted 3 benchmark files that were out-of-spec

## [0.4.31] — 2026-03-30

### Changed
- **`--model claudecode`**: removed `--claudecode` flag; use `--model claudecode` to route both BricksEngine and RawLLMEngine through ClaudeCodeProvider — cleaner single-flag API
- `validate_model_env()` silently skips `'claudecode'` (no API key required)
- `_build_providers()` replaced by single `_build_provider(model)` — both engines share one provider instance
- Benchmark CLI help and epilog updated to reflect new design

## [0.4.30] — 2026-03-30

### Added
- **`--model` CLI flag** on benchmark runner: `--model gpt-4o-mini`, `--model gemini/gemini-2.0-flash`, `--model ollama/llama3` — any LiteLLM model string, API key auto-detected from env
- **`validate_model_env()`**: warns (not hard-fails) when expected API key is missing for the chosen model; Ollama silently skipped
- **Split provider design**: `--claudecode` + `--model` coexist — BricksEngine uses ClaudeCodeProvider, RawLLMEngine uses `--model` for fair comparison
- **Model in metadata**: `run_metadata.json` `ai_model` field now reflects the actual `--model` value instead of hardcoded constant
- **`BENCHMARK_DESIGN.md` model variance note**: documents reference model, multi-provider examples

### Changed
- `write_metadata()` accepts `model: str` parameter (default: `DEFAULT_MODEL`)
- `run_benchmark()` accepts `model: str` parameter; passes separate compose/baseline providers
- Benchmark log header now shows compose and baseline provider labels explicitly

## [0.4.29] — 2026-03-30

### Added
- **`Engine` ABC** in `showcase/engine.py`: `solve(task_text, raw_data) → EngineResult` — pluggable solver interface
- **`BricksEngine`**: compose(task_text) → load(YAML) → execute(raw_data) → dict outputs; `solve_reuse()` for zero-token reuse
- **`RawLLMEngine`**: sends task + raw_data directly to LLM, parses JSON response; handles JSON parse failure gracefully
- **`EngineResult` / `BenchmarkResult` dataclasses**: identical output shape for both engines
- **`run_scenario(engine, task) → BenchmarkResult`**: single unified pipeline used by all three CRM scenarios
- **Side-by-side display** in `run_crm_pipeline()` — shows actual vs expected per key with ✓/✗ markers
- **`BENCHMARK_DESIGN.md`**: documents unified pipeline flowchart, scenario table, and design rationale
- **`test_engine.py`**: unit tests for Engine ABC, EngineResult, BenchmarkResult, RawLLMEngine (JSON parse, fence strip, failure)

### Changed
- **`crm_scenario.py`** fully rewritten: all three scenarios use `run_scenario(engine, task)` with both engines
- **`run.py`**: instantiates `BricksEngine` and `RawLLMEngine` from the same provider; passes both to scenario functions
- **Fairness fix**: `RawLLMEngine` now receives `task_text + raw_api_response` (same data as Bricks) — benchmark is now scientifically valid

## [0.4.28] — 2026-03-30

### Removed
- **`mcp/` module** entirely: `AgentRunner`, `AgentResult`, `ToolCallRecord`, `TaskGenerator`, `tool_executor`, `report`, and all A/C/D scenarios — superseded by CRM compose benchmark
- **`test_apples.py`** (753 lines) and mcp unit tests (`test_tool_executor.py`, `test_task_generator.py`)
- **6 `apples_to_apples/` result directories** from historical runs
- **`check_no_tools_answer()`** from `result_writer.py` — text-scan baseline replaced by structured `check_correctness()`
- **`Scenario` enum** (A/C/D) from `constants.py`
- **`--mode` CLI flag** — benchmark is always compose mode now
- **`_ProviderRunner`** and **`run_benchmark()`** (tool_use runner) from `run.py`

### Changed
- `run.py` is now CRM-only: `expand_scenarios()` simplified, docstring updated, `run_benchmark()` → compose-only
- `crm_scenario.py`: removed `runner` parameter and no-tools baseline from `run_crm_pipeline` / `run_crm_hallucination`
- `showcase/README.md`: rewritten to describe CRM compose benchmark

## [0.4.27] — 2026-03-30

### Added
- **`CompletionResult` dataclass** in `bricks.llm.base`: `text`, `input_tokens`, `output_tokens`, `model`, `duration_seconds`, `estimated` fields
- **`LLMProvider.complete()` returns `CompletionResult`** (was `str`) — real tokens from LiteLLM API, estimated tokens from ClaudeCodeProvider (tiktoken or char/4 fallback)
- **Optional tiktoken dependency** for `bricks-provider-claudecode[tokens]`
- **Non-zero token counts** now flow through `BlueprintComposer` into benchmark results

### Changed
- `LiteLLMProvider.complete()` extracts `response.usage.prompt_tokens` / `completion_tokens`, sets `estimated=False`
- `ClaudeCodeProvider.complete()` estimates tokens via `_estimate_tokens()`, sets `estimated=True`, `model="claude-code"`
- `_ProviderRunner.run_without_tools()` now reports actual estimated token counts instead of zeros

## [0.4.26] — 2026-03-30

### Added
- **Structured logging** across all Bricks namespaces: `bricks.ai.composer`, `bricks_provider_claudecode.provider`, `bricks_benchmark.showcase.*` — all emit to a shared `benchmark_live.log` (DEBUG) and console (INFO)
- **Dual-output log setup**: `_setup_logger()` now configures all three namespace roots so every child logger goes to the same file and stream

### Fixed
- **ClaudeCodeProvider stdin delivery**: prompt now sent via `input=` (stdin) instead of CLI argument, avoiding OS argument-length limits on large prompts
- **ClaudeCodeProvider UTF-8**: added `encoding="utf-8"` to subprocess call, fixing Windows cp1252 encoding error on Unicode chars (→) in system prompt
- **ClaudeCodeProvider default timeout**: increased from 60s to 120s
- **CRM benchmark correctness**: removed `top_plan` from expected outputs (no stdlib brick can reduce group_by output to a plan-name string); benchmark now checks `active_count`, `total_active_revenue`, `avg_active_revenue` — all three pass CORRECT
- **No more print() in pipeline**: all `print()` in `crm_scenario.py` and `run.py` replaced with `logger.*` calls

## [0.4.25] — 2026-03-30

### Added
- **100 stdlib bricks** (95 → 100): `round_number`, `truncate_string`, `is_empty_list`, `days_until`, `mask_string`
- **End-to-end smoke test** (`tests/test_smoke.py`): mocked (CI) + live (`--live`) versions
- **README rewrite**: user-facing docs targeting LangChain/CrewAI developers — install, quick start, MCP setup, why, community packs
- **Starter config**: `examples/agent.yaml` with comments for every field
- **Starter skill**: `examples/skill.md` — CRM skill description template

## [0.4.24] — 2026-03-30

### Added
- **ClaudeCodeProvider** (`packages/provider-claudecode/`): new `LLMProvider` that routes calls through `claude -p` CLI — zero API cost on Max plan
  - Auto-detects git-bash on Windows (`CLAUDE_CODE_GIT_BASH_PATH`)
  - Unsets `CLAUDECODE` env var to allow nested invocation inside active session
- **Live test mode**: `pytest --live` flag + `llm_provider` fixture in `tests/conftest.py`
  - All live tests marked `@pytest.mark.live`, skipped by default
  - Live tests in `tests/live/`: compose, execute, reuse/cache scenarios
  - `live` marker registered in `pyproject.toml`
- **CRM benchmark fixes** in `packages/benchmark/`:
  - `crm_scenario.py`: use `input_keys=["raw_api_response"]` + fix `exec_inputs` construction
  - `crm_generator.py`: enrich `task_text` with full input format description

## [0.4.23] — 2026-03-27

### Changed
- **Monorepo restructure**: split single flat package into three independently-publishable packages under `packages/`
  - `packages/core/` — `pip install bricks` (core engine, CLI, AI, MCP, orchestrator)
  - `packages/stdlib/` — `pip install bricks-stdlib` (95 stdlib bricks, auto-registers via `bricks.packs` entry point)
  - `packages/benchmark/` — `pip install bricks-benchmark` (benchmark suite)
- `bricks_stdlib.register(registry)` replaces `build_stdlib_registry()` — called automatically by entry point discovery
- `bricks.packs.discover_and_load(registry)` — new module that scans `bricks.packs` entry points at boot
- `Bricks.default()`, `from_config()`, `from_skill()` use `discover_and_load` instead of importing stdlib directly
- Root `pyproject.toml` is now a dev workspace config (pytest `pythonpath`, mypy, ruff); no `[project]` section
- Dev setup: `python -m pip install -e packages/core[dev,ai,mcp] && python -m pip install -e packages/stdlib`

---

## [0.4.22] — 2026-03-27

### Added
- `bricks store seed <dir>` CLI command: loads YAML blueprints from a directory into the file store (dev mode — 0 LLM calls on cache hit)
- `bricks store list` CLI command: lists blueprints in the file store
- `blueprints/crm_pipeline.yaml`, `blueprints/crm_hallucination.yaml`, `blueprints/crm_reuse.yaml` — pre-baked CRM benchmark blueprints
- `tests/cli/test_store_seed.py` — 4 tests covering seed, update, skip-invalid, and missing-dir

---

## [0.4.21] — 2026-03-27

### Added
- `bricks/mcp/server.py` — async `run_mcp_server(engine)` function: starts a stdio MCP server exposing the `execute_task` tool
- `bricks serve` CLI command — launches the MCP server with optional `--config` (agent.yaml) or `--model` flags
- `mcp = ["mcp>=1.0"]` optional dependency group in `pyproject.toml`; also added `all` extra combining `ai` + `mcp`
- `examples/mcp_config.json` — Claude Desktop configuration snippet for the `bricks` MCP server
- `examples/mcp_usage.md` — setup and usage guide for the MCP server
- `tests/mcp/test_server.py` — 3 unit tests for `execute_task` tool and `EXECUTE_TASK_SCHEMA`

---

## [0.4.20] — 2026-03-27

### Added
- `InputMapper` class (`bricks/orchestrator/input_mapper.py`): auto-maps user input keys to blueprint variable names (single-key, positional, exact-match strategies)
- `compose(input_keys=)` parameter hints the LLM to use user-supplied key names in blueprint `inputs:` section
- `RuntimeOrchestrator.execute()` passes input keys to composer and runs `InputMapper` before engine execution
- `BricksInputError` raised with helpful message when key count mismatch cannot be resolved

---

## [0.4.19] — 2026-03-27

### Added
- `bricks/llm/` package — pluggable `LLMProvider` abstraction with `LLMProvider` ABC and `LiteLLMProvider` implementation
- `bricks/errors.py` — public-facing error hierarchy: `BricksError`, `BricksConfigError`, `BricksComposeError`, `BricksExecutionError`, `BricksInputError`
- `Bricks.default()` class method — zero-config entry point, reads `BRICKS_MODEL` env var, accepts custom `provider=`
- `litellm>=1.0` added to `[ai]` optional dependencies
- 3 new test modules: `tests/llm/test_provider.py`, plus 2 new tests in `tests/test_api.py`

### Changed
- `BlueprintComposer.__init__` now accepts `provider: LLMProvider` instead of `api_key`/`model`
- `RuntimeOrchestrator.__init__` accepts optional `provider: LLMProvider` parameter
- `SystemBootstrapper.__init__` accepts optional `provider: LLMProvider` parameter
- All production code no longer imports `anthropic` directly; `LiteLLMProvider` routes through `litellm`

---

## [0.4.18] — 2026-03-27

### Added
- `bricks/api.py` — `Bricks` public Python class with `from_config()`, `from_skill()`, and `execute()` methods
- `Bricks` exported from `bricks` top-level package: `from bricks import Bricks`
- `from_config(path)` — boots from `agent.yaml` with zero LLM calls; defaults registry to full stdlib
- `from_skill(path)` — boots from `skill.md` with one LLM call; same registry default
- `execute(task, inputs)` — delegates to `RuntimeOrchestrator.execute()`; custom `BrickRegistry` supported
- `examples/python_api.py` — minimal boot + execute demo
- `examples/langchain_integration.py` — wrapping `Bricks` as a LangChain `Tool`
- 6 new tests in `tests/test_api.py`

---

## [0.4.17] — 2026-03-27

### Added
- `bricks/stdlib/` package — 95 production-grade bricks across 7 categories, all using Python stdlib only (no external deps)
  - `data_transformation` (25 bricks): JSON/CSV/XML parsing, dict operations, filtering, sorting, grouping, aggregates
  - `string_processing` (20 bricks): templates, regex, cleaning, case conversion, PII redaction, Levenshtein distance
  - `math_numeric` (10 bricks): divide, modulo, abs, min, max, power, percentage, clamp, ceil, floor
  - `date_time` (10 bricks): parse/format/diff/add dates, timezone conversion, business-day check, date ranges
  - `validation` (10 bricks): email, URL, phone, range, pattern, keys, numeric-string, ISO date, comparison
  - `list_operations` (10 bricks): unique, flatten, chunk, zip, intersect, difference, reverse, head, map, sum
  - `encoding_security` (10 bricks): base64, URL encode/decode, SHA-256/MD5 hashing, HTML escape, UUID, random strings
- `build_stdlib_registry() -> BrickRegistry` — one-call registry builder used by CRM benchmark
- 106 new tests across `tests/stdlib/` (one per brick)
- `benchmark/showcase/crm_generator.py` — deterministic 50-record CRM dataset with expected outputs
- `benchmark/showcase/crm_scenario.py` — CRM-pipeline, CRM-hallucination, CRM-reuse scenario runners
- CRM benchmark scenarios available via `--scenario CRM-pipeline/CRM-hallucination/CRM-reuse`
- `tzdata` dependency added for Windows timezone support

---

## [0.4.16] — 2026-03-27

### Added
- `bricks/boot/` package — `SystemBootstrapper` reads `agent.yaml` (zero LLM calls) or `skill.md` (one LLM call) and returns a `SystemConfig`
- `SystemConfig` Pydantic model — `name`, `description`, `brick_categories`, `tags`, `model`, `api_key`, `store`, `max_selector_results`
- `bricks/orchestrator/` package — `RuntimeOrchestrator` wires selector → composer → engine; single `execute(task, inputs) → dict` call
- `bricks/mcp/` package — framework-agnostic `execute_task()` tool + `EXECUTE_TASK_SCHEMA` JSON schema for MCP registration
- `OrchestratorError` exception — raised when composition or execution fails in the orchestrator
- 23 new tests across `tests/boot/` and `tests/orchestrator/`

---

## [0.4.15] — 2026-03-26

### Added
- `bricks/selector/` package — tiered brick selection system
- `BrickQuery` Pydantic model — structured query with `categories`, `tags`, `keywords`, `input_types`, `output_types`
- `SelectionTier` ABC — pluggable scoring interface; swap or extend tiers without changing the caller
- `KeywordTier` — Tier 1 deterministic scorer: matches task keywords against brick name, description, tags, and category (zero cost)
- `EmbeddingProvider` ABC + `EmbeddingTier` — Tier 2 cosine-similarity scorer; activates only on Tier 1 miss; off by default
- `TieredBrickSelector(BrickSelector)` — runs tiers in order; first tier with results wins; safe fallback to full registry on 0 results
- `TieredBrickSelector.select_query()` — accept a pre-built `BrickQuery` directly (bypasses tokenisation)
- `SelectorConfig` in `BricksConfig` — `max_results` (default 20), `embedding_provider` (default empty = Tier 1 only)
- 27 new tests in `tests/selector/test_tiered_selector.py`

---

## [0.4.14] — 2026-03-26

### Added
- `bricks/store/` package — `BlueprintStore` ABC with `MemoryBlueprintStore` (session) and `FileBlueprintStore` (persistent) backends
- `StoredBlueprint` Pydantic model — `name`, `yaml`, `fingerprints`, `created_at`, `last_used`, `use_count`
- `task_fingerprint(task)` — deterministic SHA-256 fingerprint for cache key
- `DuplicateBlueprintError` exception — raised on name collision in store
- `StoreConfig` in `BricksConfig` — `enabled`, `backend`, `path`, `ttl_days` (off by default)
- `BlueprintComposer(store=...)` parameter — cache check before LLM call; auto-save after validation; `cache_hit: bool` on `ComposeResult`
- `FileBlueprintStore.purge_stale(ttl_days)` — removes blueprints unused beyond TTL
- System prompt rule: "Use a descriptive, unique blueprint name"
- 31 new tests in `tests/store/test_blueprint_store.py`

---

## [0.4.13] — 2026-03-26

### Added
- `check_no_tools_answer()` in `result_writer.py` — scans no-tools LLM response text for expected numeric values (text search, no code execution)
- `BaselineRecord.no_tools_correct: bool` — persisted in per-scenario JSON result files
- Console and log output now shows `answer=CORRECT / WRONG` for no-tools baseline runs
- `no_tools.final_answer` threaded through `a2_complexity._compare()` so tool_use mode can also check no-tools answer

---

## [0.4.12] — 2026-03-25

### Fixed
- Correctness check false negative: `expected_outputs` was the full intermediate-step dict from `TaskGenerator`; now filtered to only keys present in `actual_outputs` before comparison and storage

---

## [0.4.11] — 2026-03-25

### Summary
Blueprint inputs declaration + retry with task context (Mission 020). Fixes two bugs from v0.4.10 benchmark: `${inputs.X}` rejected due to missing `inputs:` section, and retry hallucinating values because it lacked the original task text.

### Fixed
- System prompt now shows `inputs:` section in format block — LLM declares task parameters
- `_RETRY_PROMPT` includes original task text so LLM has real values on retry
- `_build_example()` generates worked example with `inputs:` section and `${inputs.X}` references
- `run_benchmark_compose()` passes `bp_def.inputs` to `engine.run()` instead of empty dict

### Changed
- `BlueprintDefinition.inputs` type changed from `dict[str, str]` to `dict[str, Any]` — YAML values (float, int, str) parsed natively
- New rule in system prompt: "Declare all task parameters in the inputs section"

---

## [0.4.10] — 2026-03-25

### Summary
Structured benchmark data collection (Mission 019). Every benchmark run now writes a per-scenario JSON file with full prompt/response data, per-call token counts, correctness checks against expected outputs, and no-tools baseline ratios.

### Added
- `benchmark/showcase/result_writer.py` — `ScenarioResult`, `CallRecord`, `ExecutionRecord`, `TotalRecord`, `BaselineRecord` Pydantic models + `write_scenario_result()` + `check_correctness()`
- `CallDetail` gains `system_prompt` and `user_prompt` fields (composer sets both per call)
- `ComposeResult` gains `system_prompt` field (set by `compose()`)
- `AgentResult` gains `system_prompt` field (set by `run_without_tools()` and `run_with_bricks()`)
- Per-scenario structured JSON written to run directory (e.g. `A-25_compose.json`)
- Correctness checker compares actual vs expected outputs with float tolerance
- New tests: `test_result_writer.py` (17 tests — model serialization, correctness, write/read roundtrip)

### Changed
- `run_benchmark_compose()` builds `ScenarioResult` and writes JSON per scenario
- `run_benchmark()` (tool_use mode) builds `ScenarioResult` and writes JSON per scenario
- `compose()` populates `system_prompt` on result and per-call prompts on `CallDetail`
- `run_without_tools()` and `run_with_bricks()` populate `system_prompt` on `AgentResult`

---

## [0.4.9] — 2026-03-23

### Summary
Production-grade polish + parametric benchmark (Mission 018). Major refactor: parametric `TaskGenerator` replaces hardcoded tasks, `tool_executor.py` extracted from `agent_runner.py`, `showcase/run.py` split into 4 files, shared `constants.py` with enums, private schema functions made public, deprecated aliases moved to `compat.py`, engine `_execute_step` extracted, `__all__` added.

### Added
- `benchmark/constants.py` — `Scenario`, `RunMode`, `RunStatus` enums + shared constants
- `benchmark/mcp/scenarios/task_generator.py` — `TaskGenerator` + `GeneratedTask` for parametric N-step tasks
- `benchmark/mcp/tool_executor.py` — extracted tool execution logic from `agent_runner.py`
- `benchmark/showcase/formatters.py` — table printing, cost estimation, compose call logging
- `benchmark/showcase/metadata.py` — git info, SDK version, metadata file writing
- `benchmark/showcase/registry_factory.py` — `build_registry(required_bricks)` parametric builder
- `bricks/compat.py` — deprecated Sequence* aliases with `DeprecationWarning`
- `--steps N` CLI arg for specifying step count (`--scenario A --steps 12`)
- New tests: `test_task_generator.py`, `test_tool_executor.py`, `test_formatters.py`, `test_enums.py` (47 new tests)

### Changed
- **Scenario naming**: `A2-3/6/12` → `A-N` (parametric), `C2` → `C`, `D2` → `D`
- **CLI presets**: `--scenario A` runs presets 5, 25, 50 (was 3, 6, 12)
- `showcase/run.py` — split from 622 lines into 4 files, each under 200 lines
- `agent_runner.py` — imports constants from `benchmark/constants.py`, tool execution from `tool_executor.py`
- `schema.py` — `_output_keys` → `output_keys`, `_parse_description_keys` → `parse_description_keys`, `_signature_params` → `signature_params` (now public)
- `schema.py` — safe repr for param defaults (try/except with str() fallback)
- `engine.py` — extracted `_execute_step()`, `_execute_brick_step()`, `_execute_sub_blueprint_step()` from monolithic `_execute()`
- `bricks/core/__init__.py` — exports new public schema functions, `__all__` cleaned up
- `bricks/__init__.py` — added `__all__`
- `composer.py` — updated to use public `output_keys`, `parse_description_keys` imports
- Scenario runners (`a2_complexity.py`, `c2_reuse.py`, `d2_determinism.py`) — parametric API, import constants

### Removed
- Hardcoded `TASK_A2_3`, `TASK_A2_6`, `TASK_A2_12` constants (replaced by `TaskGenerator`)
- `_build_math_registry_a3/a6/a12` functions (replaced by `build_registry`)
- Magic string constants (`DEFAULT_MODEL`, `_MODEL`, pricing) from scattered files

---

## [0.4.8] — 2026-03-19

### Summary
Eliminate retry via output key table + worked example in system prompt (Mission 017). Added `output_key_table()` for explicit output-key reference and `_build_example()` for auto-generated 2-step worked examples showing exact `${save_as.key}` chaining syntax. Target: 1 API call, 0 retries.

### Added
- `output_key_table(registry)` in `bricks/core/schema.py` — aligned table mapping brick names → output field keys
- `_parse_description_keys(description)` — regex fallback extracting keys from `{key: type}` patterns in descriptions
- `_build_example(registry)` in `bricks/ai/composer.py` — auto-generates 2-step worked YAML example
- `_build_literal_params()`, `_build_ref_params()` — helpers for worked example generation
- Tests: `TestOutputKeyTable` (4 tests) in `test_schema.py`

### Changed
- `_COMPOSE_SYSTEM` prompt — added `{output_keys}` table, `{example}` worked example, and output-key rule
- `compose()` — formats output key table and worked example into system prompt
- `bricks/core/__init__.py` — exports `output_key_table`

---

## [0.4.7] — 2026-03-19

### Summary
Single-call YAML generation — no tool_use (Mission 016). Rewrote `BlueprintComposer` to generate Blueprint YAML in 1 LLM call (max 2 on retry), eliminating multi-turn tool_use overhead. Added `BrickSelector` protocol for Stage 1 brick filtering, `ComposeResult` Pydantic model for structured output, and `--mode compose` benchmark flag.

### Added
- `bricks/core/selector.py` — `BrickSelector` ABC + `AllBricksSelector` (Stage 1 filtering)
- `ComposeResult` Pydantic model with task, YAML, validation status, token counts
- `--mode compose` flag on benchmark CLI (`python -m benchmark.showcase.run --live --mode compose`)
- `run_benchmark_compose()` — compose-mode benchmark runner with comparison table
- Tests: `test_selector.py` (3 tests), rewritten `test_composer.py` (11 tests), CLI mode flag tests

### Changed
- `BlueprintComposer` — complete rewrite: single-call text generation with 1-retry on validation failure, no tool_use
- `BlueprintComposer.__init__` — now takes `api_key, model, selector` (no registry in init)
- `BlueprintComposer.compose()` — new signature `compose(task, registry) -> ComposeResult`
- `bricks/ai/__init__.py` — exports `ComposeResult`
- `bricks/core/__init__.py` — exports `AllBricksSelector`, `BrickSelector`
- CLI `compose` command updated for new `ComposeResult` API

### Removed
- Old `compose_with_usage()` method (replaced by `ComposeResult` fields)
- Old `_build_bricks_context()` method (replaced by `compact_brick_signatures()`)

---

## [0.4.6] — 2026-03-18

### Summary
LLM-Optimized Brick Descriptions (Mission 014). Updated all showcase brick descriptions to include exact output field names in `{curly braces}`, formulas, and default values. Created `BRICK_STYLE_GUIDE.md` with 7 rules for writing machine-optimized descriptions. Added programmatic validation tests.

### Added
- `bricks/BRICK_STYLE_GUIDE.md` — 7-rule reference for writing LLM-optimized brick descriptions
- Test: `test_descriptions_include_output_keys` — validates all showcase bricks mention output fields in `{}`
- Test: `test_descriptions_under_120_chars` — validates description conciseness

### Changed
- `multiply` description: `"Multiply a * b. Returns {result: a*b}."`
- `add` description: `"Add a + b. Returns {result: a+b}."`
- `subtract` description: `"Subtract b from a. Returns {result: a-b}."`
- `round_value` description: `"Round value to N decimal places (default decimals=2). Returns {result: rounded_value}."`
- `format_result` description: `"Format as 'label: value' display string. Returns {display: str} — NOTE: output key is 'display', not 'result'."`
- `http_get` description + `category="data"` + `tags=["network", "http"]`
- `json_extract` description + `category="data"` + `tags=["data", "json"]`

---

## [0.4.5] — 2026-03-18

### Summary
Zero-Discovery Blueprint: Inject Brick Pool + Actionable Errors (Mission 013). Eliminates the `list_bricks` discovery turn by injecting compact brick signatures into the system prompt. Adds actionable error messages with fuzzy-matched suggestions and available brick/variable lists so the agent corrects mistakes in one retry.

### Added
- `compact_brick_signatures(registry)` in `bricks/core/schema.py` — generates one-liner brick signatures for system prompt injection (~50 tokens for 5 bricks vs ~500+ for JSON)
- `_signature_params()` and `_signature_output()` helpers for formatting brick signatures
- `build_apples_system(registry)` in `benchmark/mcp/scenarios/__init__.py` — builds dynamic system prompt with optional brick pool injection
- `_validation_hint()` helper — parses validation errors to suggest fixes (fuzzy brick name matching, available save_as names)
- `_fuzzy_match()` helper — substring/prefix matching for brick name suggestions
- `_extract_save_as_names()` helper — extracts save_as names from blueprint YAML
- `_brick_param_hint()` helper — formats expected params for error hints
- Actionable error handling for `BlueprintValidationError`, `BrickNotFoundError`, `VariableResolutionError`, `BrickExecutionError`, `YamlLoadError` in `_execute_tool`
- 12 new tests: compact signatures (5), actionable errors (5), build_apples_system (2)

### Changed
- `APPLES_SYSTEM` prompt rewritten: removes `list_bricks` from workflow, adds brick pool injection section
- `run_with_bricks()` now uses dynamic system prompt with injected brick signatures
- `bricks/skills/AGENT_PROMPT.md` updated for no-discovery workflow (bricks provided in context)

### Baseline (v0.4.4 — before these changes)
| Scenario | No Tools | Bricks | Ratio | Bricks turns |
|----------|----------|--------|-------|--------------|
| A2-12    | 1,746    | 13,896 | 8.3x  | 5            |

Re-run with `python -m benchmark.showcase.run --live --scenario A2-12` to measure improvement.

---

## [0.4.4] — 2026-03-18

### Summary
Agent Skill Prompt + Enriched Brick Metadata (Mission 011). Reduces agent turns and token waste by teaching the optimal Bricks workflow upfront and enriching `list_bricks()` with category, input keys, and output keys so agents can pick bricks without extra `lookup_brick` calls.

### Added
- `bricks/skills/AGENT_PROMPT.md` — system prompt snippet for any agent (<500 tokens)
- `category` parameter on `@brick()` decorator (default: `"general"`)
- `category` field on `BrickMeta` model
- `category` field on `BaseBrick.Meta`
- `input_keys` and `output_keys` in `brick_schema()` / `list_bricks()` response
- `_output_keys()` helper in `schema.py` for extracting output field names
- Tests for category field, enriched list_bricks, AGENT_PROMPT.md validation

### Changed
- `APPLES_SYSTEM` prompt rewritten to incorporate Agent Skill Prompt content (streamlined workflow, enriched metadata references)
- Showcase math bricks: added `category="math"`
- Showcase string bricks: added `category="string"`

### Baseline (v0.4.2 — before these changes)
| Scenario | No Tools | Bricks | Ratio | Bricks turns |
|----------|----------|--------|-------|--------------|
| A2-3     | 1,407    | 7,151  | 5.1x  | 4            |
| A2-6     | 1,638    | 32,036 | 19.6x | 10           |
| A2-12    | 1,746    | 23,899 | 13.7x | 7            |

Re-run with `python -m benchmark.showcase.run --live` to measure improvement.

---

## [0.4.3] — 2026-03-18

### Summary
Benchmark UX overhaul (Mission 012). Removed legacy benchmark entirely, redesigned CLI with granular `--scenario` flag, added real-time per-turn logging with token counts and timing, summary tables, and total cost estimation.

### Added
- Granular `--scenario` flag: accepts `all`, `A2`, `A2-3`, `A2-6`, `A2-12`, `C2`, `D2`
- Multiple `--scenario` values supported: `--scenario A2-3 --scenario C2`
- Per-turn real-time logging with token counts and timing per API call
- Summary table per A2 scenario with no_tools vs bricks comparison
- Total token cost estimation printed at end of run
- `on_turn` callback support in `AgentRunner.run_without_tools()` and `run_with_bricks()`
- `expand_scenarios()` helper for CLI flag parsing
- `_estimate_cost()` helper for token cost estimation
- New tests: CLI scenario expansion, cost estimation, on_turn callbacks, error handling

### Removed
- Legacy benchmark code: `benchmark/showcase/scenarios/` (complexity_curve, session_cache, determinism)
- Legacy live runner: `benchmark/showcase/live.py`
- Legacy blueprints: `benchmark/showcase/blueprints/`
- Legacy token counter: `benchmark/showcase/tokens.py`
- Legacy CLI flags: `--scenario A/C/D`, `--apples`, `--all`
- Legacy output writers: `_print_curve_table`, `_write_json`, `_write_markdown`, `_write_chart`, `_write_determinism_report`
- Legacy scenario runners: `run_scenario_a/c/d()`, `run_scenario_a/c/d_live()`
- Legacy tests: `benchmark/tests/test_showcase.py`
- Estimated mode (no `--live` = error with help message)

### Changed
- `--live` is now required (no estimated mode)
- `benchmark/showcase/run.py` rewritten as apples-only entry point
- `benchmark/showcase/README.md` rewritten for new CLI and output format
- A2/C2/D2 scenario runners now accept `on_turn` callback and return input/output token breakdowns

---

## [0.4.2] — 2026-03-18

### Summary
Apples-to-Apples Benchmark (Mission 010). True comparison: same agent, same task, same model, same system prompt — the only variable is whether Bricks MCP tools are available. Uses Anthropic's native `tool_use` API to simulate MCP tools locally (no server required).

### Added
- `benchmark/mcp/` package: `AgentRunner`, `AgentResult`, `ToolCallRecord`
- `AgentRunner.run_without_tools()` — single-turn, no tools, agent writes Python
- `AgentRunner.run_with_bricks()` — multi-turn loop with `list_bricks`, `lookup_brick`, `execute_blueprint`; tool responses served by real Bricks engine
- `_execute_tool()` — routes tool calls to `TieredCatalog` / `BlueprintEngine` / `BlueprintLoader` / `BlueprintValidator`
- `benchmark/mcp/scenarios/`: `a2_complexity`, `c2_reuse`, `d2_determinism` scenario modules
- `benchmark/mcp/report.py`: `write_apples_json()`, `write_apples_markdown()`
- `--apples` flag: run apples-to-apples benchmark only (requires `--live`)
- `--all` flag: run both legacy and apples-to-apples benchmarks
- Results written to `apples_to_apples/` subfolder inside run directory
- 13 new tests in `benchmark/tests/test_apples.py`

### Changed
- `benchmark/showcase/README.md`: "Known Limitation" section replaced with "Apples-to-Apples Benchmark" section and "Legacy Benchmark" note

---

## [0.3.2] — 2026-03-18

### Summary
Configurable Result Verbosity (Mission 007, Phase 2). `BlueprintEngine.run()` now returns a structured `ExecutionResult` with optional per-step trace detail, timing, and inputs — controlled by a `Verbosity` enum.

### Added
- `Verbosity` enum (`MINIMAL` / `STANDARD` / `FULL`) in `bricks/core/models.py`
- `StepResult` model — per-step name, brick name, inputs, outputs, timing, save_as
- `ExecutionResult` model — `outputs`, `steps`, `total_duration_ms`, `blueprint_name`, `verbosity`
- `--verbosity` / `-v` flag on `bricks run` CLI command
- 21 new tests in `tests/core/test_verbosity.py`

### Changed
- **Breaking**: `BlueprintEngine.run()` return type changed from `dict[str, Any]` to `ExecutionResult`; callers that need the raw dict use `.outputs`
- All example and benchmark caller files updated to `.outputs`

---

## [0.3.1] — 2026-03-18

### Summary
Tiered Catalog (Mission 006, Phase 2). Smart three-tier brick discovery for AI agents — replaces full registry dumps with a focused, progressive view.

### Added
- `TieredCatalog` class in `bricks/core/catalog.py`
  - Tier 1: `common_set` (user-configured, always shown)
  - Tier 2: `lookup_brick(query)` — case-insensitive search by name, tag, or description; adds hits to session cache
  - Tier 3: session cache — recently accessed bricks included in `list_bricks()`
  - `get_brick(name)` — exact fetch by name; raises `BrickNotFoundError` if missing
  - `clear_session_cache()` — reset Tier 3
- `CatalogConfig` model in `bricks/core/config.py` with `common_set: list[str]` field
- `BricksConfig.catalog: CatalogConfig` field (configurable via `bricks.config.yaml`)
- `catalog_schema(catalog)` in `bricks/core/schema.py` — returns visible bricks + AI usage hint
- All exports added to `bricks/core/__init__.py`
- 19 new tests in `tests/core/test_catalog.py`

---

## [0.3.0] — 2026-03-18

### Summary
Sub-blueprint execution (Mission 005, Phase 2). Blueprints can now call other blueprints as child steps, enabling hierarchical composition.

### Added
- `StepDefinition.blueprint` field — path to a child blueprint YAML file
- `StepDefinition.brick` is now optional (exactly one of `brick`/`blueprint` must be set; enforced by Pydantic `model_validator`)
- `BlueprintEngine` dispatches sub-blueprint steps: loads and executes the child blueprint, passes `params` as child inputs, stores child outputs under `save_as`
- Recursion depth guard (`_MAX_DEPTH = 10`); exceeding it raises `BrickExecutionError`
- `BlueprintValidator` checks sub-blueprint file existence (skips brick-registry check for blueprint steps)
- `blueprint_schema()` now includes `"blueprint"` field in step entries
- `examples/sub_blueprint.py` — runnable demo of parent/child blueprint composition
- 14 new tests in `tests/core/test_sub_blueprint.py`

### Changed
- `BlueprintEngine.__init__` accepts optional `loader: BlueprintLoader` parameter

---

## [0.2.1] — 2026-03-18

### Summary
Teardown hooks (Mission 004). On step failure, the engine calls teardown before re-raising, then reverse-teardowns all previously completed steps.

### Added
- `BaseBrick.teardown(inputs, metadata, error)` — optional no-op hook; override for cleanup
- `@brick(teardown=fn)` — attach a teardown callable `(inputs: dict, error: Exception) -> None` to a function brick
- `BrickFunction` Protocol now declares `__brick_teardown__` attribute
- `BlueprintEngine` calls teardown on the failing step, then reverse-teardowns completed steps (rollback semantics)
- Teardown exceptions are suppressed — original `BrickExecutionError` is always what propagates
- 10 new tests in `tests/core/test_teardown.py`

---

## [0.2.0] — 2026-03-18

### Summary
Rename Sequence → Blueprint everywhere (Mission 003). Pure mechanical rename — no logic changes.

### Changed
- `SequenceDefinition` → `BlueprintDefinition` (`bricks/core/models.py`)
- `SequenceEngine` → `BlueprintEngine` (`bricks/core/engine.py`)
- `SequenceLoader` → `BlueprintLoader` (`bricks/core/loader.py`)
- `SequenceValidator` → `BlueprintValidator` (`bricks/core/validation.py`)
- `SequenceValidationError` → `BlueprintValidationError` (`bricks/core/exceptions.py`)
- `SequenceComposer` → `BlueprintComposer` (`bricks/ai/composer.py`)
- `sequence_schema` → `blueprint_schema` (`bricks/core/schema.py`)
- `SequencesConfig` → `BlueprintsConfig` (`bricks/core/config.py`)
- `sequence_to_yaml` → `blueprint_to_yaml` (`bricks/core/utils.py`)
- CLI, tests, examples, benchmark, and docs updated throughout
- `examples/yaml_sequence.py` renamed to `examples/yaml_blueprint.py`
- `examples/sequences/` renamed to `examples/blueprints/`

### Backward Compatibility
- Deprecated aliases added in `bricks/core/__init__.py` and `bricks/ai/__init__.py`
- Old names (`SequenceDefinition`, `SequenceEngine`, etc.) still work until v1.0.0

---

## [0.1.1] — 2026-03-17

### Summary
Enhanced benchmark suite with complexity curve, unique run folders, and reproducibility metadata.

### Added
- Scenario A redesigned as a 3-level complexity curve: A-3 (room area), A-6 (property price), A-12 (full valuation)
- `add` and `subtract` bricks in `benchmark/showcase/bricks/math_bricks.py`
- `property_price.yaml` (6-step Blueprint) and `property_valuation.yaml` (12-step Blueprint)
- Unique timestamped run folder per benchmark execution: `run_YYYYMMDD_HHMMSS_vX.Y.Z/`
- `run_metadata.json` — captures version, model, git commit, OS, command for reproducibility
- `benchmark.log` — full execution trace written on every run
- `benchmark/tests/test_showcase.py` — 21 tests covering new bricks and all scenarios

### Changed
- Scenario C updated to use A-6 Blueprint with 10 property input sets (was room dimensions)
- Scenario D updated to use A-6 Blueprint (property price, 4 required functions)
- `results.json` restructured: `complexity_curve` / `reuse` / `determinism` top-level keys
- Benchmark README rewritten for new 3-scenario structure

### Removed
- Scenario B (API pipeline) — removed entirely

---

## [0.1.0] — 2026-03-17

### Summary
Initial benchmark release. Core engine stable with 290 tests. Full benchmark suite (A/B/C/D) with live API results. Code review complete.

### Added
- Benchmark showcase with 4 scenarios: token comparison (A/B/C) + determinism proof (D)
- Live API benchmark mode (`--live`) with real Anthropic API calls
- `BrickFunction` Protocol in `bricks/core/brick.py` for typed `__brick_meta__` access
- `bricks/core/constants.py` — shared `_REF_PATTERN` regex
- `bricks/core/utils.py` — shared `strip_code_fence()` and `sequence_to_yaml()`
- `build_showcase_registry()` helper in `benchmark/showcase/bricks/__init__.py`
- `CODEGEN_SYSTEM` shared prompt in `benchmark/showcase/scenarios/__init__.py`
- `bricks/py.typed` PEP 561 marker
- `__all__` exports in all benchmark `__init__.py` files
- Google-style docstrings on all benchmark helper functions

### Changed
- `SequenceValidator.validate()` return type: `list[str]` → `None` (raises on error)
- `_REF_PATTERN` regex moved from `resolver.py` + `validation.py` to `constants.py`
- `bricks/core/loader.py` and `config.py`: `open(path, ...)` → `path.open()`
- `bricks/core/discovery.py`: bare `except Exception: pass` → `logger.warning()`
- `benchmark/showcase/bricks/data_bricks.py`: `dict()` → `copy.deepcopy()` for `http_get`
- `benchmark/showcase/bricks/data_bricks.py`: added error handling in `json_extract`
- `benchmark/showcase/run.py`: bare `assert logger` → `if logger is None: raise RuntimeError`
- `from __future__ import annotations` added to `exceptions.py`
- `pyproject.toml`: `anthropic>=0.40` → `anthropic>=0.45`
- `pyproject.toml`: expanded ruff rules (added UP, B, SIM, RUF, C4, PTH, S, PLC, PLE)
- `pyproject.toml`: `testpaths` now includes `benchmark/tests`

### Removed
- `check_models.py` (debug script moved out of project root)
- Duplicated `_sequence_to_yaml()`, `_strip_fences()`, `_CODEGEN_SYSTEM` across files

### Security
- Added SECURITY comment to `exec()` in `benchmark/runner.py`
- `bricks/cli/main.py`: checks `ANTHROPIC_API_KEY` env var before interactive prompt
