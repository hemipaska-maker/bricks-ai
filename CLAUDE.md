# CLAUDE.md -- Bricks

## Project Overview

Bricks is a deterministic execution engine where typed Python building blocks (Bricks) are composed into auditable YAML blueprints -- by engineers directly or by AI through natural language conversation -- with full validation before execution.

## Safety Rules

**CRITICAL — read these before doing ANYTHING:**

1. **NEVER create, delete, or move files outside the Code/ directory.** Your workspace is Code/ only. Research files and project docs are NOT yours to touch. **Exception:** you may update the `## Results` section of mission files in `../.missions/` after completing a mission — nothing else in those files.
2. **NEVER run destructive commands.** The following are strictly banned:
   - `rm -rf` (on any directory)
   - `git clean -fdx` or `git clean -f`
   - `git checkout .` or `git restore .` (on entire repo)
   - `git reset --hard`
   - Any command that deletes directories recursively
3. **CLI allow-list.** You may ONLY run these commands:
   - **git:** `git status`, `git checkout`, `git add`, `git commit`, `git push`, `git tag`, `git log`, `git diff`, `git branch`, `git fetch`, `git rebase`
   - **git BANNED:** `git merge` (use `gh pr merge` instead), `git push origin main` (merge via PR only)
   - **GitHub CLI:** `gh run list`, `gh run watch`, `gh run view`, `gh pr create`, `gh pr merge`, `gh pr list`, `gh pr view`, `gh issue`
   - **General:** `cd`, `ls`, `cat`, `head`, `tail`, `grep`, `find`
   - **Python:** `pip install`, `python -m pytest`, `python -m mypy`, `python -c`
   - **Lint:** `ruff check`, `ruff format`
   - If a command is not on this list, **do not run it** without asking the user first.
4. **CI verification is MANDATORY.** After every push (to main OR any branch), you MUST verify the GitHub Actions pipeline passes:
   ```bash
   gh run list --branch <branch> --limit 1
   gh run watch --exit-status
   ```
   **BLOCKING:** Do NOT merge, do NOT proceed to the next mission, do NOT update the Results section until CI is green. If CI fails: read the logs with `gh run view <run-id> --log-failed`, fix the issue, push again, and re-verify. Repeat until green. **A mission is not done until CI passes.**

## Environment Setup

**MANDATORY — before starting ANY mission:**

1. Check if a venv exists in your repo root: `ls .venv/`
2. If not, create one: `python -m venv .venv`
3. Activate it: `source .venv/bin/activate` (Linux) or `.venv\Scripts\activate` (Windows)
4. Install all packages in dev mode:
   ```bash
   pip install -e packages/core -e packages/stdlib -e packages/benchmark -e packages/provider-claudecode
   ```
5. Verify: `python -c "import bricks; print(bricks.__version__)"`

**Always run ALL commands inside the venv.** Never install packages globally. If you see `ModuleNotFoundError`, check that the venv is active first.

## Technical Constraints

- **Cross-platform: Linux AND Windows.** All code must work on both. Use `pathlib.Path` not `os.path`. No hardcoded `/` or `\` separators. No Linux-only or Windows-only commands in code. Test paths with both forward and back slashes.
- **Python 3.10+** -- use modern syntax (`X | Y` unions, `match`, etc.)
- **Runtime dependencies:** pydantic v2, typer, ruamel.yaml
- **Type hints everywhere** -- code must pass `mypy --strict`
- **Docstrings** -- all public classes, methods, and functions require clear docstrings
- **Pydantic v2** -- all data models use `pydantic.BaseModel`

## Public API

```python
from bricks.core import brick, BaseBrick, BrickModel, BrickRegistry

registry = BrickRegistry()

@brick(tags=["hardware"], destructive=False)
def read_temperature(channel: int) -> float:
    return sensor.read(channel)

registry.register("read_temperature", read_temperature, read_temperature.__brick_meta__)
```

### Key Behaviors

- `@brick(...)` -- decorator attaching metadata to a function brick
- `BaseBrick` -- abstract base class for class-based bricks with Meta/Input/Output inner classes
- `BrickRegistry` -- flat namespace; duplicate names raise `DuplicateBrickError`
- `BlueprintEngine.run()` -- executes a `BlueprintDefinition` step-by-step
- `BlueprintValidator.validate()` -- dry-run validation without execution
- `ReferenceResolver` -- expands `${variable}` references in step parameters

### Teardown Hooks

Bricks support optional cleanup on failure:

```python
# Class-based: override teardown() in BaseBrick
class MyBrick(BaseBrick):
    def teardown(self, inputs: BrickModel, metadata: BrickMeta, error: Exception) -> None:
        # cleanup (close connections, delete temp files, etc.)
        ...

# Function-based: pass teardown= to @brick
def my_cleanup(inputs: dict, error: Exception) -> None:
    ...

@brick(tags=["io"], destructive=True, teardown=my_cleanup)
def write_to_file(path: str, content: str) -> dict:
    ...
```

The engine calls teardown on the failing step, then reverse-teardown all previously completed steps before re-raising. Teardown exceptions are suppressed so they never mask the original error.

## Monorepo Structure

```
bricks/                  # Python package root
  core/                  # Engine, context, validation, Brick base
    brick.py             # @brick decorator + BaseBrick + BrickModel
    registry.py          # BrickRegistry
    models.py            # Pydantic models (BrickMeta, StepDefinition, BlueprintDefinition)
    engine.py            # BlueprintEngine
    context.py           # ExecutionContext
    resolver.py          # ${variable} reference resolver
    validation.py        # Dry-run validation
    exceptions.py        # All custom exceptions
  cli/                   # Typer CLI commands
    main.py              # Typer app with command stubs
  ai/                    # AI composition layer
    composer.py          # BlueprintComposer
tests/                   # Mirrors source structure
examples/                # Runnable standalone scripts
```

## Commands

```bash
# Run tests
python -m pytest
python -m pytest -q --tb=short

# Type checking
python -m mypy packages/core/src/bricks --strict

# Lint & format
ruff check .
ruff format .

# Run CLI
bricks --help

# Git (worktree-safe — never touch main locally)
git fetch origin --prune
git checkout -b mission-XXX-short-name origin/main
git status
git add <specific files>
git commit -m "Mission XXX: description"
git tag vX.Y.Z
git push origin mission-XXX-short-name --tags
git checkout origin/main --detach
git branch -d <branch>
git log --oneline -10
git diff

# GitHub CLI (PR-based merge)
gh pr create --title "Mission XXX: description" --fill
gh pr merge --merge
gh run list --branch <branch> --limit 1
gh run watch --exit-status
gh run view <run-id> --log-failed
gh pr list / view
gh issue create / list / view
```

## Code Conventions

### Naming & Structure
- `snake_case` for functions/variables, `PascalCase` for classes
- Keep modules small and focused -- one responsibility per file
- Tests mirror source structure in `tests/` (e.g., `tests/core/test_brick.py`)
- All exceptions inherit from `BrickError`
- Decorator returns unwrapped functions -- no behavior change

### Pythonic Code Standards
Write professional, idiomatic Python. Every piece of code should look like it belongs in a well-maintained open-source library.

**Functions & Methods:**
- Single responsibility -- a function does ONE thing, named as a verb (`validate_blueprint`, not `blueprint_validator_logic`)
- Max 30 lines per function. If longer, extract helpers with clear names
- Use early returns to avoid deep nesting: `if not x: return` over `if x: <100 lines of code>`
- Use `*args` and `**kwargs` only when genuinely needed (e.g., decorators). Be explicit about parameters
- Type hints on ALL parameters and return values -- no exceptions
- Default mutable arguments: NEVER `def f(x=[])`, always `def f(x: list[str] | None = None)`

**Docstrings:**
- Google style docstrings on all public functions, classes, and methods
- Include `Args:`, `Returns:`, `Raises:` sections. No lazy one-liners on public API
- Private helpers (`_foo`) need at least a one-line docstring explaining intent

**Data & Control Flow:**
- Prefer list/dict/set comprehensions over manual loops when the intent is clear
- Use `pathlib.Path` over `os.path` everywhere
- Use `contextlib.suppress(Exception)` over bare `try/except: pass`
- Use `enum.Enum` for fixed choices, not string constants scattered in code
- Use `dataclasses` or Pydantic models for structured data, never raw dicts passed between functions
- Raise specific exceptions over generic ones -- no silent failures, no bare `except:`

**Testing:**
- Use `pytest` fixtures, not setUp/tearDown
- One assert per test when possible -- name the test after what it asserts (`test_multiply_returns_product`)
- Use `pytest.raises` for expected exceptions, `pytest.mark.parametrize` for variant inputs
- Test edge cases: empty inputs, None, negative numbers, boundary values
- No magic numbers in tests -- use named constants or fixtures
- **Seam rule:** If your mission creates or modifies a data class that crosses module boundaries (e.g., a result object produced in module A and consumed in module B), you MUST write at least one test that instantiates it in the *consumer* module with a real value — not just in the producer. This catches "field added but never wired through" bugs that unit tests miss.
- **Integration rule:** If your mission touches any pipeline boundary (compose → execute, DSL → engine, MCP → runtime), you MUST include at least one end-to-end test that passes a real input value through the full chain and asserts correct output. Mocking at the boundary is not sufficient.
- **Live run rule:** If your mission fixes an integration bug or touches the compose → execute boundary, run the affected benchmark scenario once with `--live` before opening the PR and paste the output in the mission Results section. Example: `.venv/Scripts/python -m bricks_benchmark.showcase.run --live --scenario <affected-scenario> --model claudecode`. If no benchmark scenario covers your change, the CI smoke test is sufficient.

**Imports:**
- Group: stdlib → third-party → local, separated by blank lines
- Use `from __future__ import annotations` in every module
- Prefer absolute imports (`from bricks.core.models import ...`) over relative

**Error Messages:**
- Include the offending value: `f"Brick {name!r} not found"` not `"Brick not found"`
- Include context: `f"Step {step.name!r}: brick {step.brick!r} not found in registry"`
- Suggest fixes when possible: `f"Did you mean {closest_match!r}?"`

## Git Workflow

### Worktree Awareness

**You are running in a git worktree, NOT the main checkout.** The `main` branch is checked out in another directory (`Code/`). You CANNOT check out or merge into `main` locally — git will reject it. All merges to `main` happen remotely via GitHub PRs.

**You NEVER use a `dev` branch.** There are only two states for you:
1. **Working:** on a feature branch (`mission-XXX-short-name`)
2. **Idle:** detached HEAD on `origin/main`

### Branch Naming

| Mission Type | Branch Format | Example |
|---|---|---|
| Numbered mission | `mission-XXX-short-name` | `mission-042-repo-hygiene` |
| Bench mission | `bench/XXX-short-name` | `bench/003-log-parser` |

### Starting a Mission

```bash
# 1. Sync with remote (picks up other coders' changes)
git fetch origin --prune

# 2. Create feature branch from latest main
git checkout -b mission-XXX-short-name origin/main

# 3. Pre-flight check — verify codebase is healthy BEFORE you start
python -m pytest --tb=short -q
python -m mypy packages/core/src/bricks --strict
ruff check .
```

If pre-flight fails and the failures are NOT from your code: **STOP. Report to CTO. Do not fix other coders' bugs without a mission.**

### Finishing a Mission (Merge Process)

```bash
# 1. Run full verification suite
python -m pytest --tb=short -q
python -m mypy packages/core/src/bricks --strict
ruff check .

# 2. Stage and commit (specific files only, never git add -A)
git add <specific files>
git commit -m "Mission XXX: description"

# 3. SYNC before version bump — another coder may have merged while you worked
git fetch origin
git rebase origin/main
#    This gets the latest __version__ and CHANGELOG.md from main.
#    If rebase conflicts: resolve, `git rebase --continue`, re-run tests.
#    ONLY after rebase do you read the current version number.

# 4. Bump version in pyproject.toml + bricks/__init__.py
#    Read current __version__ from bricks/__init__.py (post-rebase!), increment patch by 1
git add <version files>
git commit -m "Bump version to vX.Y.Z"

# 5. Tag the version
git tag vX.Y.Z

# 6. Push branch + tag to GitHub
git push origin mission-XXX-short-name --tags

# 7. Create PR via GitHub CLI
gh pr create --title "Mission XXX: description" --fill

# 8. Wait for CI to pass on the branch — BLOCKING
gh run list --branch mission-XXX-short-name --limit 1
gh run watch --exit-status
#    If CI fails: read logs with `gh run view <run-id> --log-failed`
#    Fix, push, wait for CI again. Repeat until green.

# 9. Merge PR remotely (NOT local merge)
gh pr merge --merge

# 10. Fill in the mission Results section
#     Update Status to ✅ Done at TOP of file AND in Results section at bottom
```

**CRITICAL:** Never run `git checkout main`, `git merge ... main`, or `git push origin main`. All of these will fail or cause conflicts because `main` is checked out in the other worktree.

### Between Missions (Idle State)

After a mission is merged, reset to idle state:

```bash
# 1. Sync with remote
git fetch origin --prune

# 2. Detach from the merged branch
git checkout origin/main --detach

# 3. Clean up the old branch
git branch -d mission-XXX-short-name
```

You are now on detached HEAD with the latest code. When the next mission arrives, start from "Starting a Mission" above. If time has passed, `git fetch origin --prune` again before creating the new branch.

### What If Another Coder Pushed While You Were Working?

If your PR can't merge because `main` has moved:

```bash
# Rebase your branch on latest main
git fetch origin
git rebase origin/main
# Resolve any conflicts, then force-push your branch
git push origin mission-XXX-short-name --force-with-lease
# Wait for CI again, then merge
```

## Versioning

- Scheme: semantic versioning -- `0.PHASE.PATCH`
- `0.x.0` = phase completion (major milestone)
- `0.0.x` = feature or fix within a phase
- Version lives in two places (always keep in sync): `pyproject.toml` `version` field and `bricks/__init__.py` `__version__`
- Every version bump gets a git tag matching the new version

**Versioning rule for missions:** Mission files never specify a target version number. At the end of each mission, Claude Code reads the current `__version__` from `bricks/__init__.py` and increments the patch by 1. The PM tab does not set versions — the coder is the single source of truth.

**GitHub push rule:** After every commit and tag, push your branch (never main directly):
```bash
git push origin mission-XXX-short-name --tags
```
Then merge via `gh pr merge --merge`. The tag and commits flow to main through the PR. Every mission must end with the PR merged and CI green on main. No exceptions.

## File Maintenance Contract

After every version bump, update: `pyproject.toml`, `bricks/__init__.py`, `CHANGELOG.md`, git tag, push to GitHub.
After every phase completion, also update: `CLAUDE.md`, `README.md`.
After any rename (e.g., Sequence -> Blueprint), update ALL of: `CLAUDE.md`, `README.md`, `CHANGELOG.md`.

## Research Knowledge Base

After every mission, update the relevant files in `../research/` (one level above Code):
- `../research/BENCHMARK_TRACKER.md` — log any new benchmark run with raw numbers and version
- `../research/DECISIONS_LOG.md` — log any new architecture decision with options and rationale
- `../research/KNOWN_ISSUES.md` — add new issues discovered, mark resolved ones
- `../research/AGENT_EFFICIENCY_RESEARCH.md` — update results table if agent token/turn metrics changed
- `../research/SKILL_PORTABILITY.md` — update if any component's model-agnostic status changes

## Benchmark Reproducibility

The benchmark runner must embed `bricks.__version__` in ALL output: `results.json`, `summary.md`, `determinism_report.md`, stdout.

## Missions

**Mission files live OUTSIDE the Code directory** at `../.missions/`. You may READ mission files but NEVER delete, move, or modify them (see Safety Rule #1).

**MANDATORY — after completing ANY mission, you MUST do BOTH of the following:**

1. **Update the `**Status:**` field at the TOP of the mission file** — change it from `🔵 Ready` or `🔄 In Progress` to `✅ Done`. This is the first thing the PM checks. If you only update the Results section at the bottom but leave the top status unchanged, the PM will miss your completed work.
2. **Fill in the `## Results` section** at the bottom — set Status to ✅ Done, record the Completed date, the Version, list files changed, and paste test results.

**Both updates are required. No exceptions. This is how the PM verifies your work.**

When the user says **"new mission"**, do the following:
1. Read `../.missions/PROTOCOL.md`
2. Find the highest-numbered `MISSION_XXX.md` file in `../.missions/`
3. Read it and execute the task
4. When done: update the **Status field at the top** AND fill in the **Results section at the bottom** — this step is not optional
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 