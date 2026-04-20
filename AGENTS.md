# AGENTS.md

## Overview
Bricks is a Python library for deterministic LLM orchestration. It lets you compose small, reliable building blocks ("bricks") into pipelines that handle structured data work LLMs are bad at alone.

## Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

## Pre-commit
pip install pre-commit
pre-commit install

## Commands
Test all:        pytest
Test one:        pytest tests/path/to/test_x.py::test_name
Lint:            ruff check . && ruff format --check .
Typecheck:       mypy src/bricks
Run CLI:         bricks --help
Run benchmark:   bricks-bench

## Architecture
- `src/bricks/core/` — engine, context, DSL pipeline
- `src/bricks/stdlib/` — standard bricks (text, data, logic)
- `src/bricks/benchmark/` — benchmark suite + web GUI
- `src/bricks/providers/` — LLM provider adapters
See docs/architecture.md for detail.

## Conventions
- Python 3.10+, type hints everywhere, docstrings on public APIs
- ruff for format/lint (enforced in CI)
- Imports: stdlib → third-party → local
- Tests in tests/, mirror src/ layout

## Git Workflow
1. Pick an Issue from the active milestone
2. Branch: feat/issue-<num>-short-desc or fix/issue-<num>-short-desc
3. Commit with conventional prefix: feat:, fix:, chore:, docs:
4. Open PR, link Issue with "Closes #<num>"
5. CI must be green. No merge without green.
6. Squash-merge to main.

## Release
Do NOT bump versions manually. release-please opens a release PR automatically based on conventional commits. Merge that PR to trigger PyPI publish.

## Common Pitfalls
- Don't edit CHANGELOG.md — release-please handles it
- Don't push to main — branch protection will reject it
- Run `pre-commit` hook before pushing (ruff check + format)
- mypy is strict. Don't suppress without a comment explaining why.

## Asking Questions
Comment on the Issue you're working on. Tag @hemipaska.
