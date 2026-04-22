"""Tests for issue #66 bug B — public ``Bricks`` default registry must ship builtins.

``Bricks.default()`` → ``_build_default_registry()`` previously called
``discover_and_load`` for stdlib packs but never registered the DSL
control-flow builtins (``__for_each__`` / ``__branch__``). Any composed
blueprint that wrapped iteration crashed on the first ``registry.get``
lookup. The showcase path worked only because it registered builtins
manually; the public API didn't.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from bricks.api import Bricks, _build_default_registry
from bricks.core.engine import BlueprintEngine
from bricks.core.models import BlueprintDefinition, StepDefinition


def test_build_default_registry_includes_control_flow_builtins() -> None:
    """The registry backing ``Bricks.default()`` must have both DSL
    builtins so composed blueprints never crash with
    ``BrickNotFoundError: '__for_each__'``."""
    reg = _build_default_registry()
    assert reg.has("__for_each__"), "__for_each__ missing — for_each blueprints would fail"
    assert reg.has("__branch__"), "__branch__ missing — conditional blueprints would fail"


def test_bricks_default_registry_runs_for_each_blueprint() -> None:
    """End-to-end: a hand-built ``__for_each__`` blueprint must run
    through the default registry without ``BrickNotFoundError``."""

    def double(item: int) -> dict[str, int]:
        return {"result": item * 2}

    # Pass an explicit mock provider so Bricks.default() skips the
    # real LiteLLMProvider construction (which would need an API key).
    bricks = Bricks.default(provider=MagicMock())

    # Register a test brick into the live registry so __for_each__ can
    # look it up mid-iteration.
    from bricks.core.models import BrickMeta

    bricks.registry.register(
        "double",
        double,
        BrickMeta(name="double", description="Double an int", category="test"),
    )

    bp = BlueprintDefinition(
        name="map_double",
        steps=[
            StepDefinition(
                name="map",
                brick="__for_each__",
                params={
                    "items": [1, 2, 3],
                    "do_brick": "double",
                    "item_kwarg": "item",
                    "static_kwargs": {},
                    "on_error": "fail",
                },
                save_as="map",
            ),
        ],
        outputs_map={"result": "${map.result}"},
    )

    engine = BlueprintEngine(registry=bricks.registry)
    result = engine.run(bp, inputs={})
    assert result.outputs == {"result": [{"result": 2}, {"result": 4}, {"result": 6}]}
