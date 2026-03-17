# My Workflow & Skill Document
> Generated from the Bricks project -- a deterministic execution engine for typed Python building blocks.

---

## 1. Tech Stack

| Layer | Tool | Version |
|---|---|---|
| Language | Python | 3.10+ |
| Type checking | mypy | `--strict` mode |
| Linter | ruff | target: py310 |
| Formatter | ruff format | -- |
| Test runner | pytest | 9.x |
| Build backend | setuptools | >=68.0 |
| Validation | pydantic | v2 |
| CLI | typer | >=0.9 |
| YAML parser | ruamel.yaml | >=0.18 |
| Package distribution | PyPI via `pyproject.toml` | PEP 621 |
| Source hosting | GitLab | -- |

**Key constraint:** Synchronous execution model (async designed for later).

---

## 2. Project Structure

```
bricks/
├── bricks/                   # Main package (monorepo with internal boundaries)
│   ├── __init__.py           # Package version
│   ├── core/                 # Engine, context, validation, Brick base
│   │   ├── __init__.py       # Public API exports for core
│   │   ├── brick.py          # @brick decorator + BaseBrick + BrickModel
│   │   ├── registry.py       # BrickRegistry
│   │   ├── exceptions.py     # All custom exceptions
│   │   ├── models.py         # Pydantic models
│   │   ├── context.py        # ExecutionContext
│   │   ├── engine.py         # BlueprintEngine
│   │   ├── validation.py     # Dry-run validation
│   │   └── resolver.py       # ${variable} resolver
│   ├── cli/                  # Typer CLI
│   │   ├── __init__.py
│   │   └── main.py           # Typer app with command stubs
│   └── ai/                   # AI composition layer
│       ├── __init__.py
│       └── composer.py       # BlueprintComposer stub
├── tests/                    # Mirrors source structure exactly
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_brick.py
│   │   ├── test_registry.py
│   │   ├── test_exceptions.py
│   │   ├── test_models.py
│   │   ├── test_context.py
│   │   ├── test_engine.py
│   │   ├── test_validation.py
│   │   └── test_resolver.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── test_main.py
│   └── ai/
│       ├── __init__.py
│       └── test_composer.py
├── examples/
│   └── basic_usage.py
├── pyproject.toml
├── CLAUDE.md
├── MY-WORKFLOW.md
└── README.md
```

**Principle:** One responsibility per module. Monorepo with clean internal boundaries (core/, cli/, ai/).

---

## 3. Code Standards

### Naming
- **Files/modules:** `snake_case` (`registry.py`, `resolver.py`)
- **Classes:** `PascalCase` (`BrickRegistry`, `BlueprintEngine`)
- **Functions/variables:** `snake_case` (`resolve_reference`, `step_index`)
- **Private attributes:** single leading underscore (`_bricks`, `_results`)
- **Test files:** `test_<module>.py`, mirroring source

### Type Hints
- **Everywhere** -- all function signatures, all return types, all class attributes
- Use modern union syntax: `X | Y` (Python 3.10+) instead of `Union[X, Y]`
- Use `from __future__ import annotations` at the top of files that need forward references
- Use `Callable[..., Any]` when a function's exact signature is not relevant
- Must pass `mypy --strict` -- no exceptions
- Use `pydantic.mypy` plugin for Pydantic v2 compatibility

### Docstrings
- Required on all public classes, methods, and functions
- Format: one-line summary, blank line, then `Args:` / `Returns:` / `Raises:` sections
- Private helpers don't require docstrings

### Imports
- Group imports: stdlib -> third-party (pydantic, typer, ruamel.yaml) -> internal (`from bricks.core.x import Y`)
- `core/__init__.py` re-exports the public API; users import from `bricks.core`, not submodules

```python
# Good
from bricks.core import brick, BaseBrick, BrickRegistry

# Avoid
from bricks.core.brick import brick
```

### Formatting (ruff)
- Rules selected: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `N` (naming), `W` (warnings)
- `ruff format .` handles all whitespace/style automatically

---

## 4. Patterns & Practices

### Error Handling
- **Specific exceptions over generic ones** -- all inherit from `BrickError`
- Custom exceptions in a dedicated `exceptions.py`
- Exception carries structured data as attributes (e.g., `err.name`, `err.reference`)
- Engine wraps brick execution in try/catch, raising `BrickExecutionError`

### Decorator Pattern (@brick)
- `@brick(...)` is a decorator factory returning a decorator
- The decorator returns the original function **unwrapped** -- no behaviour change
- Attaches a `BrickMeta` Pydantic model as `__brick_meta__` attribute

### Class-Based Brick Pattern
- Subclass `BaseBrick` with inner classes `Meta`, `Input(BrickModel)`, `Output(BrickModel)`
- Implement `execute(self, inputs, metadata) -> dict`
- Pydantic validates Input/Output automatically

### Validation-First
- `BlueprintValidator.validate()` checks everything before execution
- `bricks dry-run` uses this for CLI-level dry runs
- Always validate, then execute

### Testing
- **Test classes group related tests** (`TestRegister`, `TestResolve`)
- `BrickRegistry.clear()` resets state between tests
- `tmp_path` pytest fixture for filesystem tests
- Tests mirror source structure: `tests/core/test_brick.py` for `bricks/core/brick.py`

---

## 5. Workflow Process

### Step 1 -- Understand before touching anything
Read all source files before suggesting or making changes. Never modify code that hasn't been read.

### Step 2 -- Plan before implementing non-trivial changes
For anything touching multiple files or requiring architectural decisions, enter plan mode.

### Step 3 -- Implement in focused chunks
Work on one file at a time. Mark tasks complete immediately after finishing.

### Step 4 -- Verify end-to-end
After every change:
```bash
pytest                    # all tests pass
mypy bricks --strict      # no type errors
ruff check .              # no lint issues
python examples/*.py      # examples actually run
```

### Step 5 -- Save context to memory
After learning the project, write key facts to a persistent memory file so future sessions don't start from scratch.

---

## Quick Reference -- Commands

```bash
# Development setup
pip install -e ".[dev]"

# Daily workflow
pytest                    # run tests
mypy bricks --strict      # type check
ruff check .              # lint
ruff format .             # format

# CLI
bricks --help             # show commands
bricks list               # list registered bricks
bricks dry-run seq.yaml   # validate without executing
bricks run seq.yaml       # execute a sequence

# Before publishing
python -m build
twine check dist/*
twine upload dist/*
```
