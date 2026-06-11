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
Typecheck:       mypy src/bricks src/bricks_ai
Import boundary: lint-imports
Run CLI:         bricks --help
Run Playground:  bricks playground  (local web UI at http://localhost:8080)

## Architecture
Two top-level packages with a one-way dependency: `bricks_ai` imports `bricks`, never the reverse.

**`src/bricks/` — the deterministic engine (zero LLM code or deps):**
- `bricks/core/` — engine, registry, DSL pipeline, validators, context
- `bricks/stdlib/` — standard bricks (text, data, logic)
- `bricks/store/` — blueprint cache (file/memory)
- `bricks/selector/` — keyword/embedding brick selection tiers
- `bricks/boot/` — `agent.yaml` bootstrapping (YAML only)
- `bricks/cli/` — CLI; AI commands lazily import `bricks_ai` behind friendly gates

**`src/bricks_ai/` — the AI layer (everything that talks to an LLM):**
- `composer.py` / `healing.py` — LLM blueprint composition + self-heal
- `orchestrator.py` — natural-language task executor (compose → execute)
- `api.py` — the `Bricks` facade (`from bricks_ai import Bricks`)
- `skill_boot.py` — `skill.md` bootstrapping (one LLM extraction call)
- `llm/` — `LLMProvider` ABC, LiteLLM provider, shared provider factory
- `providers/` — adapters (claudecode, anthropic, openai, ollama)
- `playground/` — web GUI + FastAPI backend, scenario runner, `bricks playground run`
- `mcp/`, `demo/` — MCP server, interactive demo

The boundary is enforced by import-linter (`[tool.importlinter]` in pyproject.toml),
a guard test (`tests/core/test_no_ai_imports.py`), and the `engine-only` CI job
which installs the base package (no LLM SDKs) and runs the engine test suites.
See docs/ENGINE_AI_SPLIT_PLAN.md for the split rationale; the `pre-decoupling`
git tag marks the last coupled state.

## Conventions
- Python 3.10+, type hints everywhere, docstrings on public APIs
- ruff for format/lint (enforced in CI)
- Imports: stdlib → third-party → local
- Tests in tests/, mirror src/ layout

## README Auto-Sections
README.md has cog-driven blocks (CLI help, stdlib brick snapshot, verified example output).
- Refresh locally: `cog -r README.md`
- Pre-commit will rewrite the blocks if README.md or any source they read from changes
- CI runs `cog --check README.md` and a lychee link checker; both must be green
- To add a new block, wrap Python in `<!-- [[[cog ... ]]] -->` / `<!-- [[[end]]] -->` markers

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
