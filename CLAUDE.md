# CLAUDE.md -- Bricks

## Project Overview

Bricks is a deterministic execution engine where typed Python building blocks (Bricks) are composed into auditable YAML blueprints -- by engineers directly or by AI through natural language conversation -- with full validation before execution.

## Technical Constraints

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
pytest

# Type checking
mypy bricks --strict

# Lint
ruff check .

# Format
ruff format .

# Run CLI
bricks --help
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

**Imports:**
- Group: stdlib → third-party → local, separated by blank lines
- Use `from __future__ import annotations` in every module
- Prefer absolute imports (`from bricks.core.models import ...`) over relative

**Error Messages:**
- Include the offending value: `f"Brick {name!r} not found"` not `"Brick not found"`
- Include context: `f"Step {step.name!r}: brick {step.brick!r} not found in registry"`
- Suggest fixes when possible: `f"Did you mean {closest_match!r}?"`

## Versioning

- Scheme: semantic versioning -- `0.PHASE.PATCH`
- `0.x.0` = phase completion (major milestone)
- `0.0.x` = feature or fix within a phase
- Version lives in two places (always keep in sync): `pyproject.toml` `version` field and `bricks/__init__.py` `__version__`
- Every version bump gets a git tag matching the new version

**Versioning rule for missions:** Mission files never specify a target version number. At the end of each mission, Claude Code reads the current `__version__` from `bricks/__init__.py` and increments the patch by 1. The PM tab does not set versions — the coder is the single source of truth.

**GitHub push rule:** After every commit and tag, always push both to GitHub:
```bash
git push origin main
git push origin --tags
```
Every mission must end with both the commit and the tag live on GitHub. No exceptions.

## File Maintenance Contract

After every version bump, update: `pyproject.toml`, `bricks/__init__.py`, `CHANGELOG.md`, git tag, push to GitHub.
After every phase completion, also update: `PROGRESS.md`, `CLAUDE.md`, `MY-WORKFLOW.md`, `README.md`.
After any rename (e.g., Sequence -> Blueprint), update ALL of: `CLAUDE.md`, `MY-WORKFLOW.md`, `PROGRESS.md`, `README.md`, `CHANGELOG.md`.

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

When the user says **"new mission"**, do the following:
1. Read `.missions/PROTOCOL.md`
2. Find the highest-numbered `MISSION_XXX.md` file in `.missions/`
3. Read it and execute the task
4. Fill in the Results section when done
