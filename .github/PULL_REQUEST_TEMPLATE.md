## Mission
Mission XXX — [title]

## Changes
Brief description of what changed and why.

## Files Changed
- `path/to/file.py` — what changed

## Checklist
- [ ] Tests pass (`pytest --tb=short -q`)
- [ ] Type checks pass (`mypy packages/core/src/bricks --strict`)
- [ ] Linting passes (`ruff check . && ruff format --check .`)
- [ ] Docstrings added/updated for public API changes
- [ ] Version bumped in `pyproject.toml` + `bricks/__init__.py`
- [ ] `CHANGELOG.md` updated
- [ ] CI green on branch before merge
- [ ] **Integration test included** — if this mission touches a pipeline boundary (compose → execute, DSL → engine, MCP → runtime, any cross-module data class), at least one test runs the full chain with a real input value end-to-end (not mocked at the boundary)

## Test Results
```
<paste pytest output here>
```

## Notes
Any context for the reviewer — decisions made, things deferred, known limitations.
