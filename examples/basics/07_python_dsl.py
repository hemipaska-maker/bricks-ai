"""Example 07: Python DSL — write flows as Python, not YAML.

Instead of writing YAML blueprints, you can define pipelines directly
in Python using ``step``, ``for_each``, ``branch``, and the ``@flow`` decorator.
The DSL traces the function once at decoration time and builds a DAG.

Run this example::

    python examples/basics/07_python_dsl.py
"""

from __future__ import annotations

from bricks import branch, flow, for_each, step
from bricks.core.brick import brick
from bricks.core.registry import BrickRegistry

# ---------------------------------------------------------------------------
# Register some simple test bricks
# ---------------------------------------------------------------------------

registry = BrickRegistry()


@brick(description="Multiply a number by 2")
def double(value: float) -> float:
    """Double a value."""
    return value * 2.0


@brick(description="Add two numbers")
def add(a: float, b: float) -> float:
    """Add two floats."""
    return a + b


registry.register("double", double, double.__brick_meta__)  # type: ignore[attr-defined]
registry.register("add", add, add.__brick_meta__)  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# 1. Simple step chain
# ---------------------------------------------------------------------------


@flow
def simple_chain() -> None:
    """A simple two-step pipeline."""
    a = step.add(a=1.0, b=2.0)
    return step.double(value=a)


print("=== Simple chain ===")
print(f"Name:     {simple_chain.name}")
print(f"DAG nodes: {len(simple_chain.dag.nodes)}")
print()

# ---------------------------------------------------------------------------
# 2. for_each with a list of items
# ---------------------------------------------------------------------------


@flow
def batch_double(items: None) -> None:
    """Double every item in a list."""
    return for_each(items, do=lambda x: step.double(value=x))


print("=== Batch double (for_each) ===")
print(f"Name:     {batch_double.name}")
bp = batch_double.to_blueprint()
for s in bp.steps:
    print(f"  step: {s.name}  brick: {s.brick}")
print()

# ---------------------------------------------------------------------------
# 3. branch with a condition
# ---------------------------------------------------------------------------


@flow
def conditional_add() -> None:
    """Add 1+2 or 3+4 depending on a condition brick."""
    return branch(
        "add",
        if_true=lambda: step.add(a=1.0, b=2.0),
        if_false=lambda: step.add(a=3.0, b=4.0),
    )


print("=== Conditional (branch) ===")
print(f"Name:     {conditional_add.name}")
bp2 = conditional_add.to_blueprint()
for s in bp2.steps:
    print(f"  step: {s.name}  brick: {s.brick}")
print()

# ---------------------------------------------------------------------------
# 4. Export to YAML
# ---------------------------------------------------------------------------

print("=== YAML export ===")
print(simple_chain.to_yaml())
