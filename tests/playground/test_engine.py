"""Smoke tests for the relocated bricks_ai.playground.engine module.

After PR 2 of the playground redesign (#76) the engine moved from
``bricks_ai.playground.showcase.engine`` to ``bricks_ai.playground.engine``.
This file confirms the public ``BricksEngine`` and ``RawLLMEngine``
classes still expose the same shape that web routes + CLI rely on.
Heavyweight behavior is exercised by the existing integration tests
(``tests/integration/test_showcase_cached.py``); this file just locks
the import path and result shape.
"""

from __future__ import annotations

from bricks_ai.playground.engine import BricksEngine, EngineResult, RawLLMEngine


def test_imports_resolve() -> None:
    """The relocated module exposes the engines + result dataclass."""
    assert BricksEngine is not None
    assert RawLLMEngine is not None
    assert EngineResult is not None


def test_engine_result_has_expected_fields() -> None:
    """``EngineResult`` carries the fields web/routes.py and the CLI
    ``run`` command read on every invocation."""
    result = EngineResult(
        outputs={"x": 1},
        tokens_in=10,
        tokens_out=5,
        duration_seconds=0.1,
        model="test",
        raw_response="raw",
        dsl_code="dsl",
        error="",
    )
    assert result.outputs == {"x": 1}
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert result.dsl_code == "dsl"
    assert result.error == ""
