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
  phase (used by the ``@flow`` decorator).
- :class:`FlowDefinition` — result of the ``@flow`` decorator; holds a DAG and
  exposes ``.to_blueprint()``, ``.to_yaml()``, ``.to_dag()``, and
  ``.execute()`` methods.
- :func:`flow` — decorator that traces a function once at decoration time and
  returns a :class:`FlowDefinition`.

Nothing executes in this module beyond the trace phase inside :func:`flow`.

Example::

    from bricks import flow, step, for_each

    @flow
    def my_pipeline(data):
        \"\"\"Clean and save data.\"\"\"
        cleaned = step.clean(text=data)
        return step.save(data=cleaned)

    bp = my_pipeline.to_blueprint()
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bricks.core.dag import DAG
    from bricks.core.models import BlueprintDefinition


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
        do: Brick name string (after extraction) or raw callable for ``for_each`` nodes.
        item_kwarg: Name of the keyword the lambda binds to the iteration
            item — e.g. ``"email"`` for ``for_each(do=lambda e: step.X(email=e))``.
            Defaults to ``"item"`` when the lambda cannot be introspected.
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
    do: str | Callable[..., Any] | None = None
    item_kwarg: str = "item"
    on_error: str = "fail"

    # branch fields
    condition: str | Callable[..., Any] | None = None
    if_true: Callable[..., Any] | None = None
    if_false: Callable[..., Any] | None = None

    # DAG wiring — populated by DAGBuilder (Mission 059)
    depends_on: list[str] = field(default_factory=list)

    @property
    def output(self) -> Node:
        """Allow step1.output syntax — returns self for use as param reference.

        During @flow trace, step.X() returns a Node. LLM-generated DSL often
        chains steps via step1.output. This property makes that work by returning
        the Node itself, which DAGBuilder resolves as a dependency edge.
        """
        return self

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

    Extracts the brick name from *do* by invoking it with a mock :class:`Node`
    through an isolated :class:`ExecutionTracer`. The extracted name (a string)
    is stored on the resulting node — **not** the callable — so it serialises
    cleanly to a blueprint step.

    Args:
        items: A :class:`Node` whose output is a list, or a literal list.
        do: A callable that takes one item and returns a :class:`Node`.
            Must call exactly one ``step.brick_name(...)`` inside.
        on_error: ``"fail"`` (stop on first error, default) or ``"collect"``
            (continue processing, gather all errors).

    Returns:
        A :class:`Node` with ``type="for_each"`` and ``do`` set to the
        extracted brick name string.

    Raises:
        ValueError: If ``on_error`` is invalid or if the brick name cannot
            be extracted from the *do* callable.
    """
    if on_error not in ("fail", "collect"):
        raise ValueError(f"on_error must be 'fail' or 'collect', got {on_error!r}")

    # Extract brick name by running the lambda through an isolated tracer.
    # A fresh ExecutionTracer is used (not the module-level _tracer singleton)
    # to avoid corrupting any outer trace that may be in progress.
    import bricks.core.dsl as _dsl_module  # noqa: PLC0415

    inner_tracer = ExecutionTracer()
    outer_tracer = _dsl_module._tracer
    _dsl_module._tracer = inner_tracer
    inner_tracer.start()
    mock = Node(type="brick", brick_name="__mock__", params={})
    try:
        do(mock)
    except Exception:  # noqa: S110
        pass
    finally:
        inner_tracer.stop()
        _dsl_module._tracer = outer_tracer

    inner_nodes = inner_tracer.get_nodes()
    if not inner_nodes:
        raise ValueError(
            "for_each: could not extract brick name from do= callable. "
            "Ensure the lambda calls exactly one step.brick_name(...)."
        )
    first = inner_nodes[0]
    do_brick: str = first.brick_name or f"__{first.type}__"

    # Find the kwarg the lambda binds the iteration item to — the key in
    # the inner node's params whose value is the mock Node we injected.
    # Default to "item" for backward compatibility when the lambda doesn't
    # use the item, uses it positionally, or nests it inside an expression.
    item_kwarg: str = "item"
    for key, value in first.params.items():
        if isinstance(value, Node) and value.id == mock.id:
            item_kwarg = key
            break

    node = Node(type="for_each", items=items, do=do_brick, item_kwarg=item_kwarg, on_error=on_error)
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


class FlowDefinition:
    """A traced flow — the result of decorating a function with :func:`flow`.

    Holds the DAG produced by tracing the decorated function and exposes
    conversion and execution methods.

    Attributes:
        name: Function name used as the blueprint name.
        description: Function docstring used as the blueprint description.
        dag: The resolved :class:`~bricks.core.dag.DAG`.
        output_nodes: For multi-output flows that return a ``dict[str, Node]``,
            maps output key names to the terminal :class:`Node` objects captured
            during the structural trace.  ``None`` for single-output flows.
    """

    def __init__(
        self,
        name: str,
        description: str,
        dag: DAG,
        fn: Callable[..., Any] | None = None,
        output_nodes: dict[str, Node] | None = None,
    ) -> None:
        """Initialise with a name, description, and pre-built DAG.

        Args:
            name: Blueprint / flow name.
            description: Human-readable description.
            dag: The resolved DAG from the trace phase.
            fn: The original undecorated flow function. When provided,
                :meth:`execute` re-traces it with real inputs instead of using
                the ``None``-param DAG captured at decoration time.
            output_nodes: Optional mapping of output key → terminal Node for
                multi-output flows that return ``dict[str, Node]``.
        """
        self.name = name
        self.description = description
        self.dag = dag
        self._fn = fn
        self.output_nodes = output_nodes

    def to_dag(self) -> DAG:
        """Return the raw DAG.

        Returns:
            The :class:`~bricks.core.dag.DAG` built from the traced nodes.
        """
        return self.dag

    def to_blueprint(self) -> BlueprintDefinition:
        """Convert to a :class:`~bricks.core.models.BlueprintDefinition`.

        For multi-output flows (dict return), injects a proper ``outputs_map``
        referencing each terminal node's step by name.

        Returns:
            A blueprint ready for the existing
            :class:`~bricks.core.engine.BlueprintEngine`.
        """
        bp = self.dag.to_blueprint(name=self.name, description=self.description)
        if self.output_nodes:
            ordered = self.dag.topological_sort()
            node_id_to_step = {
                nid: f"step_{i + 1}_{self.dag.nodes[nid].brick_name or self.dag.nodes[nid].type}"
                for i, nid in enumerate(ordered)
            }
            bp.outputs_map = {
                key: f"${{{node_id_to_step[node.id]}.result}}"
                for key, node in self.output_nodes.items()
                if node.id in node_id_to_step
            }
        return bp

    def to_yaml(self) -> str:
        """Serialize to a YAML string.

        Returns:
            YAML representation of the blueprint.
        """
        from bricks.core.utils import blueprint_to_yaml  # noqa: PLC0415

        return blueprint_to_yaml(self.to_blueprint())

    def execute(
        self,
        inputs: dict[str, Any] | None = None,
        engine: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute the flow with real inputs by re-tracing and running the DAG.

        Re-traces ``_fn`` with actual runtime values so step params hold real
        data (not the ``None`` placeholders from the ``@flow`` structural
        trace). Builds a fresh DAG and runs it through the provided engine.

        Accepts runtime inputs as either a dict (``inputs={"key": value}``) or
        keyword arguments (``key=value``). Both forms are merged, with keyword
        arguments taking precedence.

        For multi-output flows (those returning ``dict[str, Node]``), the
        result dict is keyed by the declared output names. For single-output
        flows, the result has a single ``"result"`` key.

        Args:
            inputs: Optional dict of runtime inputs mapping parameter names to
                values (e.g. ``{"raw_api_response": "..."}``)
            engine: Optional :class:`~bricks.core.engine.BlueprintEngine`
                instance. When ``None``, a default engine with an empty
                :class:`~bricks.core.registry.BrickRegistry` is created —
                suitable for unit tests only. Production callers must supply
                their registry-backed engine so that brick lookups succeed.
            **kwargs: Additional runtime inputs as keyword arguments. Merged
                with ``inputs``; keyword arguments take precedence on conflict.

        Returns:
            Dict of execution outputs from the engine run.
        """
        from bricks.core.dag_builder import DAGBuilder  # noqa: PLC0415
        from bricks.core.engine import BlueprintEngine  # noqa: PLC0415
        from bricks.core.registry import BrickRegistry  # noqa: PLC0415

        merged: dict[str, Any] = {**(inputs or {}), **kwargs}

        if self._fn is not None and merged:
            _tracer.start()
            try:
                return_value = self._fn(**merged)
            finally:
                _tracer.stop()
            traced_nodes = _tracer.get_nodes()

            if isinstance(return_value, dict) and all(isinstance(v, Node) for v in return_value.values()):
                # Multi-output flow: build outputs_map from declared output keys
                dag = DAGBuilder().build(traced_nodes, root=None)
                ordered = dag.topological_sort()
                node_id_to_step = {
                    nid: f"step_{i + 1}_{dag.nodes[nid].brick_name or dag.nodes[nid].type}"
                    for i, nid in enumerate(ordered)
                }
                outputs_map = {
                    key: f"${{{node_id_to_step[node.id]}.result}}"
                    for key, node in return_value.items()
                    if node.id in node_id_to_step
                }
                bp = dag.to_blueprint(name=self.name, description=self.description)
                bp = bp.model_copy(update={"outputs_map": outputs_map})
            else:
                root = return_value if isinstance(return_value, Node) else None
                dag = DAGBuilder().build(traced_nodes, root=root)
                bp = dag.to_blueprint(name=self.name, description=self.description)
        else:
            bp = self.to_blueprint()

        resolved_engine: BlueprintEngine = engine if engine is not None else BlueprintEngine(BrickRegistry())
        result = resolved_engine.run(bp, inputs=merged)
        return dict(result.outputs)


def flow(
    func: Callable[..., Any] | None = None,
    **_kwargs: Any,
) -> FlowDefinition | Callable[..., FlowDefinition]:
    """Decorator that traces a function once and returns a :class:`FlowDefinition`.

    The decorated function is called **once at decoration time** with ``None``
    substituted for all parameters. The body should only call ``step.*``,
    :func:`for_each`, and :func:`branch` — all of which return
    :class:`Node` objects.  Actual values are irrelevant during tracing;
    only the graph structure is captured.

    Supports three call forms::

        @flow               # bare decorator
        @flow()             # empty call
        @flow(outputs_map={...})  # call with kwargs (kwargs are ignored)

    Args:
        func: The pipeline function to trace. Pass ``None`` (implicitly) when
            the decorator is called with keyword arguments.
        **_kwargs: Ignored keyword arguments — allows ``@flow(outputs_map={...})``
            without raising ``TypeError``.

    Returns:
        A :class:`FlowDefinition` when called directly on a function, or a
        single-argument decorator when called with keyword arguments.

    Example::

        from bricks import flow, step

        @flow
        def clean_pipeline(text):
            \"\"\"Clean raw text.\"\"\"
            return step.clean(text=text)

        bp = clean_pipeline.to_blueprint()
    """
    if func is None:
        return lambda f: flow(f)  # type: ignore[return-value]

    from bricks.core.dag_builder import DAGBuilder  # noqa: PLC0415

    sig = inspect.signature(func)
    mock_args = dict.fromkeys(sig.parameters)

    _tracer.start()
    try:
        return_value = func(**mock_args)
    finally:
        _tracer.stop()

    traced_nodes = _tracer.get_nodes()

    output_nodes: dict[str, Node] | None = None
    if isinstance(return_value, dict):
        if not all(isinstance(v, Node) for v in return_value.values()):
            bad = {k: type(v).__name__ for k, v in return_value.items() if not isinstance(v, Node)}
            raise TypeError(f"@flow dict return must map str keys to Node values. Non-Node values: {bad}")
        output_nodes = dict(return_value)
        root = None
    else:
        root = return_value if isinstance(return_value, Node) else None

    dag = DAGBuilder().build(traced_nodes, root=root)

    return FlowDefinition(
        name=func.__name__,
        description=func.__doc__ or "",
        dag=dag,
        fn=func,
        output_nodes=output_nodes,
    )
