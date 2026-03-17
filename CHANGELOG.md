# Changelog

All notable changes to the Bricks project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
