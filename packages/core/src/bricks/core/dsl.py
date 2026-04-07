"""Bricks Python DSL — foundational data model.

Provides the two core building blocks for the Python-first DSL:

- :class:`Node` — a universal DAG node representing a brick invocation,
  a ``for_each`` loop, or a ``branch``.
- :class:`StepProxy` — enables the ``step.brick_name(param=value)`` syntax
  that captures brick invocations as :class:`Node` objects without executing
  them.

Nothing executes in this module. It is a pure data model.

Example::

    from bricks import step

    clean_node = step.clean_text(text="hello world")
    filtered = step.filter_dict_list(items=clean_node, key="status", value="active")
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single node in the Bricks execution DAG.

    Nodes are created by :class:`StepProxy` calls (``step.brick_name(**kwargs)``)
    or by the control-flow primitives ``for_each()`` and ``branch()`` (Mission 058).

    Attributes:
        id: Auto-generated 8-char hex unique identifier.
        type: Node type — ``"brick"``, ``"for_each"``, or ``"branch"``.
        brick_name: Brick identifier (set only when ``type="brick"``).
        params: Keyword arguments passed to the brick. Values may be other
            :class:`Node` objects — dependency edges are resolved later by
            :class:`~bricks.dsl.dag_builder.DAGBuilder`.
        items: Input items for ``for_each`` nodes.
        do: Callable body for ``for_each`` nodes.
        on_error: Error policy for ``for_each`` — ``"fail"`` (default, stop on
            first error) or ``"collect"`` (continue, gather all errors).
        condition: Condition for ``branch`` nodes (brick name string in v1).
        if_true: Callable for the truthy branch.
        if_false: Callable for the falsy branch.
        depends_on: IDs of nodes this node depends on. Populated by
            :class:`~bricks.dsl.dag_builder.DAGBuilder` (Mission 059).
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: str = ""
    brick_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    # for_each fields
    items: Node | list[Any] | None = None
    do: Callable[..., Any] | None = None
    on_error: str = "fail"

    # branch fields
    condition: str | Callable[..., Any] | None = None
    if_true: Callable[..., Any] | None = None
    if_false: Callable[..., Any] | None = None

    # DAG wiring — populated by DAGBuilder (Mission 059)
    depends_on: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        """Return a concise string representation.

        Returns:
            Representation showing brick name (for brick nodes) or type,
            plus the node id.
        """
        if self.type == "brick":
            return f"Node(brick={self.brick_name!r}, id={self.id!r})"
        return f"Node(type={self.type!r}, id={self.id!r})"


class StepProxy:
    """Proxy that captures ``step.brick_name(param=value)`` as :class:`Node` objects.

    All attribute access on a :class:`StepProxy` returns a keyword-only callable.
    Calling that callable creates and returns a :class:`Node` with
    ``type="brick"``, the accessed attribute name as ``brick_name``, and the
    keyword arguments as ``params``.

    Positional arguments are rejected — brick invocations must be explicit
    (keyword-only) to keep DSL code readable and unambiguous.

    Example::

        from bricks import step

        node = step.filter_dict_list(items=data, key="status", value="active")
        assert node.brick_name == "filter_dict_list"
        assert node.params == {"items": data, "key": "status", "value": "active"}
    """

    def __getattr__(self, brick_name: str) -> Callable[..., Node]:
        """Return a keyword-only callable that creates a brick Node.

        Args:
            brick_name: The brick identifier to capture.

        Returns:
            A callable that accepts only keyword arguments and returns a
            :class:`Node` with ``type="brick"``.
        """

        def invoke_step(**kwargs: Any) -> Node:
            """Create a brick Node from keyword arguments.

            Args:
                **kwargs: Parameters to pass to the brick.

            Returns:
                A :class:`Node` representing this brick invocation.
            """
            return Node(type="brick", brick_name=brick_name, params=kwargs)

        return invoke_step


#: Module-level :class:`StepProxy` singleton. Import and use directly::
#:
#:     from bricks import step
#:     node = step.my_brick(param="value")
step: StepProxy = StepProxy()
