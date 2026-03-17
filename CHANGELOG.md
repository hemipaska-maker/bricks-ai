# Changelog

All notable changes to the Bricks project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
