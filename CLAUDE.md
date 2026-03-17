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

- `snake_case` for functions/variables, `PascalCase` for classes
- Raise specific exceptions over generic ones -- no silent failures
- Keep modules small and focused -- one responsibility per file
- Tests mirror source structure in `tests/` (e.g., `tests/core/test_brick.py`)
- All exceptions inherit from `BrickError`
- Decorator returns unwrapped functions -- no behavior change

## Versioning

- Scheme: semantic versioning -- `0.PHASE.PATCH`
- `0.x.0` = phase completion (major milestone)
- `0.0.x` = feature or fix within a phase
- Version lives in two places (always keep in sync): `pyproject.toml` `version` field and `bricks/__init__.py` `__version__`
- Every version bump gets a git tag: `v0.1.0`, `v0.2.0`, etc.
- Version map: v0.1.0 (benchmark), v0.2.0 (Phase 1), v0.3.0 (Phase 2), v0.4.0 (Phase 3), v0.5.0 (Phase 4), v1.0.0 (public release)

## File Maintenance Contract

After every version bump, update: `pyproject.toml`, `bricks/__init__.py`, `CHANGELOG.md`, git tag.
After every phase completion, also update: `PROGRESS.md`, `CLAUDE.md`, `MY-WORKFLOW.md`, `README.md`.
After any rename (e.g., Sequence -> Blueprint), update ALL of: `CLAUDE.md`, `MY-WORKFLOW.md`, `PROGRESS.md`, `README.md`, `CHANGELOG.md`.

## Benchmark Reproducibility

The benchmark runner must embed `bricks.__version__` in ALL output: `results.json`, `summary.md`, `determinism_report.md`, stdout.

## Missions

When the user says **"new mission"**, do the following:
1. Read `.missions/PROTOCOL.md`
2. Find the highest-numbered `MISSION_XXX.md` file in `.missions/`
3. Read it and execute the task
4. Fill in the Results section when done
