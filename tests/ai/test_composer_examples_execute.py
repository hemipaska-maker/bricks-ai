"""Runtime regression tests for the worked examples in ``DSL_PROMPT_TEMPLATE``.

The sister module :mod:`tests.ai.test_composer_examples` pins **syntactic**
validity (every `@flow` block passes ``validate_dsl``). This module adds
**runtime** coverage: each example is compiled to a ``BlueprintDefinition``
and executed end-to-end against a stub registry that satisfies every
``step.<brick>(...)`` call the examples make.

Origin: issue #35. The original ``crm_summary`` bug (issue #28) was a
worked example that validated but crashed at ``engine.run()`` — that bug
would have been caught by this test.

The stubs return deterministic placeholder values that are "sensible
enough" to let the example flow finish without raising. Correctness of
the final outputs is **not** asserted here — that is the per-scenario
benchmark's job.
"""

from __future__ import annotations

from typing import Any

import pytest

from bricks.ai.composer import DSL_PROMPT_TEMPLATE
from bricks.core.builtins import register_builtins
from bricks.core.dsl import FlowDefinition, branch, flow, for_each, step
from bricks.core.engine import BlueprintEngine
from bricks.core.models import BrickMeta
from bricks.core.registry import BrickRegistry
from tests.ai.test_composer_examples import _extract_examples


def _exec_example_to_flow(code: str) -> FlowDefinition:
    """Execute an example string in a DSL namespace and return its FlowDefinition."""
    namespace: dict[str, Any] = {
        "step": step,
        "for_each": for_each,
        "branch": branch,
        "flow": flow,
    }
    exec(code, namespace)  # noqa: S102 — examples are AST-validated in the sister test
    flow_def = next((v for v in namespace.values() if isinstance(v, FlowDefinition)), None)
    assert flow_def is not None, "example did not produce a FlowDefinition"
    return flow_def


# ── stub bricks ──────────────────────────────────────────────────────────────
#
# Each stub is intentionally permissive: it accepts whatever the example
# feeds it and returns a downstream-compatible shape.


def _extract_json_from_str(text: str) -> dict[str, Any]:
    return {"result": {"customers": _customers(), "tickets": _tickets()}}


def _extract_dict_field(data: Any, field: str) -> dict[str, Any]:
    if isinstance(data, dict):
        return {"result": data.get(field, [])}
    return {"result": []}


def _filter_dict_list(items: Any, key: str, value: Any) -> dict[str, Any]:
    if not isinstance(items, list):
        return {"result": []}
    return {"result": [item for item in items if isinstance(item, dict) and item.get(key) == value]}


def _count_dict_list(items: Any) -> dict[str, Any]:
    return {"result": len(items) if isinstance(items, list) else 0}


def _calculate_aggregates(items: Any, field: str, operation: str) -> dict[str, Any]:
    if not isinstance(items, list):
        return {"result": 0.0}
    values = [item.get(field, 0) for item in items if isinstance(item, dict)]
    if operation == "sum":
        return {"result": float(sum(values))}
    if operation == "avg":
        return {"result": float(sum(values) / len(values)) if values else 0.0}
    return {"result": 0.0}


def _map_values(items: Any, key: str) -> dict[str, Any]:
    if not isinstance(items, list):
        return {"result": []}
    return {"result": [item.get(key) for item in items if isinstance(item, dict)]}


def _is_email_valid(email: str) -> dict[str, Any]:
    return {"result": isinstance(email, str) and "@" in email}


def _reduce_sum(values: Any) -> dict[str, Any]:
    if not isinstance(values, list):
        return {"result": 0}
    total: int | float = 0
    for v in values:
        if isinstance(v, (int, float)):
            total += v
        elif isinstance(v, dict) and isinstance(v.get("result"), (int, float)):
            total += v["result"]
    return {"result": total}


def _generate_summary(count: Any, status: str) -> dict[str, Any]:
    return {"result": f"{status}: {count}"}


def _is_nonempty_list(input: Any) -> dict[str, Any]:
    return {"result": bool(input)}


def _customers() -> list[dict[str, Any]]:
    return [
        {"status": "active", "monthly_revenue": 100.0},
        {"status": "inactive", "monthly_revenue": 0.0},
        {"status": "active", "monthly_revenue": 50.0},
    ]


def _tickets() -> list[dict[str, Any]]:
    return [
        {"priority": "high", "customer_email": "alice@example.com"},
        {"priority": "low", "customer_email": "bob@example.com"},
        {"priority": "critical", "customer_email": "eve@example.com"},
    ]


_STUBS: dict[str, Any] = {
    "extract_json_from_str": _extract_json_from_str,
    "extract_dict_field": _extract_dict_field,
    "filter_dict_list": _filter_dict_list,
    "count_dict_list": _count_dict_list,
    "calculate_aggregates": _calculate_aggregates,
    "map_values": _map_values,
    "is_email_valid": _is_email_valid,
    "reduce_sum": _reduce_sum,
    "generate_summary": _generate_summary,
    "is_nonempty_list": _is_nonempty_list,
}


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture(name="stub_registry")
def _stub_registry() -> BrickRegistry:
    reg = BrickRegistry()
    register_builtins(reg)
    for name, fn in _STUBS.items():
        reg.register(name, fn, BrickMeta(name=name, description=f"stub for {name}"))
    return reg


def _bricks_used(code: str) -> set[str]:
    """Return the set of stdlib brick names (``step.<name>``) used in *code*."""
    import ast

    tree = ast.parse(code)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "step":
            out.add(node.attr)
    return out


# ── tests ────────────────────────────────────────────────────────────────────


def test_stubs_cover_every_brick_the_examples_use() -> None:
    """Gate the suite: any new example must either re-use a covered brick
    or add a stub. Fail with the missing brick name so the maintainer
    knows exactly what to add."""
    all_used: set[str] = set()
    for ex in _extract_examples(DSL_PROMPT_TEMPLATE):
        all_used |= _bricks_used(ex)
    missing = all_used - set(_STUBS)
    assert not missing, (
        f"_STUBS is missing a stub for {sorted(missing)!r}. Either add a "
        f"permissive stub or simplify the example in DSL_PROMPT_TEMPLATE."
    )


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_example_runs_end_to_end(idx: int, stub_registry: BrickRegistry) -> None:
    """Every worked example must execute through ``BlueprintEngine.run``
    without raising — guards against "example validates but crashes" bugs
    like #28."""
    examples = _extract_examples(DSL_PROMPT_TEMPLATE)
    code = examples[idx]

    flow_def = _exec_example_to_flow(code)
    blueprint = flow_def.to_blueprint()

    inputs: dict[str, Any] = {}
    for input_name in blueprint.inputs:
        inputs[input_name] = "{}"  # raw_api_response stub — extract_json_from_str ignores it

    engine = BlueprintEngine(registry=stub_registry)
    # The assertion *is* "did not raise". Outputs are not validated here;
    # correctness is owned by the per-scenario showcase benchmarks.
    engine.run(blueprint, inputs=inputs)
