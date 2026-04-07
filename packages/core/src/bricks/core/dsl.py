"""Bricks Python DSL — foundational data model and control-flow primitives.

Provides the core building blocks for the Python-first DSL:

- :class:`Node` — a universal DAG node representing a brick invocation,
  a ``for_each`` loop, or a ``branch``.
- :class:`StepProxy` — enables the ``step.brick_name(param=value)`` syntax
  that captures brick invocations as :class:`Node` objects without executing
  them.
- :func:`for_each` — maps a step over a list of items.
- :func:`branch` — conditional routing based on a brick's boolean output.
- :class:`ExecutionTracer` — records all Node objects created during a trace
  phase (used by the ``@flow`` decorator in Mission 060).

Nothing executes in this module. It is a pure data model.

Example::

    from bricks import step, for_each, branch

    clean_node = step.clean_text(text="hello world")
    filtered = step.filter_dict_list(items=clean_node, key="status", value="active")
    loop = for_each(items=filtered, do=lambda item: step.process(data=item))
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
    or by the control-flow primitives :func:`for_each` and :func:`branch`.

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


class ExecutionTracer:
    """Records all Node objects created during a trace phase.

    Used by the ``@flow`` decorator (Mission 060) to capture the DAG structure
    without executing any bricks. The tracer is inactive by default; call
    :meth:`start` before a trace and :meth:`stop` after.

    Example::

        from bricks.core.dsl import _tracer
        _tracer.start()
        node = step.clean(text="hi")
        _tracer.stop()
        assert len(_tracer.get_nodes()) == 1
    """

    def __init__(self) -> None:
        """Initialise with an empty node list and inactive state."""
        self.nodes: list[Node] = []
        self._active: bool = False

    def start(self) -> None:
        """Begin recording nodes, clearing any previously recorded nodes."""
        self.nodes = []
        self._active = True

    def stop(self) -> None:
        """Stop recording nodes."""
        self._active = False

    def record(self, node: Node) -> Node:
        """Record a node if tracing is active.

        Args:
            node: The node to potentially record.

        Returns:
            The node unchanged (for convenient chaining).
        """
        if self._active:
            self.nodes.append(node)
        return node

    @property
    def is_active(self) -> bool:
        """Return True if the tracer is currently recording."""
        return self._active

    def get_nodes(self) -> list[Node]:
        """Return a copy of all recorded nodes.

        Returns:
            A new list containing all nodes recorded since the last :meth:`start`.
        """
        return list(self.nodes)


#: Module-level :class:`ExecutionTracer` singleton used by all primitives.
_tracer: ExecutionTracer = ExecutionTracer()


class StepProxy:
    """Proxy that captures ``step.brick_name(param=value)`` as :class:`Node` objects.

    All attribute access on a :class:`StepProxy` returns a keyword-only callable.
    Calling that callable creates and returns a :class:`Node` with
    ``type="brick"``, the accessed attribute name as ``brick_name``, and the
    keyword arguments as ``params``. The node is also auto-recorded to the
    module-level :data:`_tracer` if it is active.

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
            node = Node(type="brick", brick_name=brick_name, params=kwargs)
            _tracer.record(node)
            return node

        return invoke_step


def for_each(
    items: Node | list[Any],
    do: Callable[[Any], Node],
    on_error: str = "fail",
) -> Node:
    """Map a step over a list of items.

    Args:
        items: A :class:`Node` whose output is a list, or a literal list.
        do: A callable that takes one item and returns a :class:`Node`.
        on_error: ``"fail"`` (stop on first error, default) or ``"collect"``
            (continue processing, gather all errors).

    Returns:
        A :class:`Node` with ``type="for_each"``.

    Raises:
        ValueError: If ``on_error`` is not ``"fail"`` or ``"collect"``.
    """
    if on_error not in ("fail", "collect"):
        raise ValueError(f"on_error must be 'fail' or 'collect', got {on_error!r}")
    node = Node(type="for_each", items=items, do=do, on_error=on_error)
    _tracer.record(node)
    return node


def branch(
    condition: str,
    if_true: Callable[[], Node],
    if_false: Callable[[], Node],
) -> Node:
    """Conditional routing based on a brick's boolean output.

    Args:
        condition: Brick name that returns a boolean. In v1, only brick name
            strings are accepted — no lambdas or arbitrary callables.
        if_true: Called when the condition brick returns ``True``.
        if_false: Called when the condition brick returns ``False``.

    Returns:
        A :class:`Node` with ``type="branch"``.

    Raises:
        TypeError: If ``condition`` is not a string (v1 restriction).
    """
    if not isinstance(condition, str):
        raise TypeError(f"In v1, condition must be a brick name string, got {type(condition).__name__}")
    node = Node(type="branch", condition=condition, if_true=if_true, if_false=if_false)
    _tracer.record(node)
    return node


#: Module-level :class:`StepProxy` singleton. Import and use directly::
#:
#:     from bricks import step
#:     node = step.my_brick(param="value")
step: StepProxy = StepProxy()
