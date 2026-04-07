"""Tests for bricks.core.dag and bricks.core.dag_builder."""

from __future__ import annotations

import pytest
from bricks.core.dag import DAG
from bricks.core.dag_builder import DAGBuilder
from bricks.core.dsl import Node, _tracer, branch, for_each, step


def _build(nodes: list[Node], root: Node | None = None) -> DAG:
    """Shortcut: build a DAG from a list of nodes."""
    return DAGBuilder().build(nodes, root=root)


def _traced(*callables: object) -> list[Node]:
    """Run callables with tracer active and return recorded nodes."""
    _tracer.start()
    for fn in callables:
        if callable(fn):
            fn()  # type: ignore[operator]
    _tracer.stop()
    return _tracer.get_nodes()


class TestDAGBuilder:
    """Tests for DAGBuilder.build()."""

    def setup_method(self) -> None:
        """Reset tracer before each test."""
        _tracer.stop()
        _tracer.nodes.clear()

    def test_dag_builder_simple_chain(self) -> None:
        """a → b(data=a) → c(data=b) produces edges b→a and c→b."""
        _tracer.start()
        a = step.load(path="data.csv")
        b = step.clean(data=a)
        c = step.save(data=b)
        _tracer.stop()
        nodes = _tracer.get_nodes()

        dag = _build(nodes)
        assert len(dag.nodes) == 3
        assert a.id in dag.edges[b.id]
        assert b.id in dag.edges[c.id]
        assert dag.edges[a.id] == []

    def test_dag_builder_no_deps(self) -> None:
        """Independent nodes have no edges."""
        _tracer.start()
        a = step.brick_a()
        b = step.brick_b()
        _tracer.stop()
        nodes = _tracer.get_nodes()

        dag = _build(nodes)
        assert dag.edges[a.id] == []
        assert dag.edges[b.id] == []

    def test_dag_builder_for_each_depends_on_items(self) -> None:
        """for_each node depends on its items node."""

        def do_fn(item: object) -> Node:
            """Dummy body."""
            return step.process(data=item)

        _tracer.start()
        data = step.load(path="input.csv")
        fe = for_each(items=data, do=do_fn)
        _tracer.stop()
        nodes = _tracer.get_nodes()

        dag = _build(nodes)
        assert data.id in dag.edges[fe.id]

    def test_dag_builder_root_is_last_node(self) -> None:
        """root_id defaults to the last node in the list."""
        _tracer.start()
        step.a()
        b = step.b()
        _tracer.stop()
        nodes = _tracer.get_nodes()

        dag = _build(nodes)
        assert dag.root_id == b.id

    def test_dag_builder_explicit_root(self) -> None:
        """Passing root= overrides the default."""
        _tracer.start()
        a = step.a()
        step.b()
        _tracer.stop()
        nodes = _tracer.get_nodes()

        dag = _build(nodes, root=a)
        assert dag.root_id == a.id


class TestTopologicalSort:
    """Tests for DAG.topological_sort()."""

    def test_topological_sort_simple_chain(self) -> None:
        """a → b → c sorts to [a, b, c]."""
        a = Node(type="brick", brick_name="a")
        b = Node(type="brick", brick_name="b")
        c = Node(type="brick", brick_name="c")
        dag = DAG(
            nodes={a.id: a, b.id: b, c.id: c},
            edges={a.id: [], b.id: [a.id], c.id: [b.id]},
        )
        order = dag.topological_sort()
        assert order.index(a.id) < order.index(b.id) < order.index(c.id)

    def test_topological_sort_independent_nodes(self) -> None:
        """Independent nodes all appear in result (deterministic order)."""
        a = Node(type="brick", brick_name="a")
        b = Node(type="brick", brick_name="b")
        dag = DAG(
            nodes={a.id: a, b.id: b},
            edges={a.id: [], b.id: []},
        )
        order = dag.topological_sort()
        assert set(order) == {a.id, b.id}
        assert len(order) == 2

    def test_topological_sort_diamond(self) -> None:
        """Diamond a→b, a→c, b→d, c→d: a first, d last."""
        a = Node(type="brick", brick_name="a")
        b = Node(type="brick", brick_name="b")
        c = Node(type="brick", brick_name="c")
        d = Node(type="brick", brick_name="d")
        dag = DAG(
            nodes={a.id: a, b.id: b, c.id: c, d.id: d},
            edges={a.id: [], b.id: [a.id], c.id: [a.id], d.id: [b.id, c.id]},
        )
        order = dag.topological_sort()
        assert order[0] == a.id
        assert order[-1] == d.id

    def test_topological_sort_cycle_raises(self) -> None:
        """A cycle raises ValueError."""
        a = Node(type="brick", brick_name="a")
        b = Node(type="brick", brick_name="b")
        dag = DAG(
            nodes={a.id: a, b.id: b},
            edges={a.id: [b.id], b.id: [a.id]},
        )
        with pytest.raises(ValueError, match="cycle"):
            dag.topological_sort()


class TestToBlueprint:
    """Tests for DAG.to_blueprint()."""

    def setup_method(self) -> None:
        """Reset tracer before each test."""
        _tracer.stop()
        _tracer.nodes.clear()

    def test_to_blueprint_simple_chain(self) -> None:
        """3-step chain produces a BlueprintDefinition with 3 steps."""
        _tracer.start()
        a = step.load(path="data.csv")
        b = step.clean(data=a)
        step.save(data=b)
        _tracer.stop()
        dag = _build(_tracer.get_nodes())

        bp = dag.to_blueprint(name="my_pipe")
        assert bp.name == "my_pipe"
        assert len(bp.steps) == 3

    def test_to_blueprint_params_resolve_to_refs(self) -> None:
        """Node references in params become ${step_name.result} strings."""
        _tracer.start()
        a = step.load(path="data.csv")
        step.clean(data=a)
        _tracer.stop()
        dag = _build(_tracer.get_nodes())

        bp = dag.to_blueprint()
        clean_step = next(s for s in bp.steps if s.brick == "clean")
        assert "${" in clean_step.params["data"]
        assert ".result}" in clean_step.params["data"]

    def test_to_blueprint_for_each_becomes_builtin(self) -> None:
        """for_each node maps to __for_each__ brick."""

        def do_fn(item: object) -> Node:
            """Dummy body."""
            return step.process(data=item)

        _tracer.start()
        data = step.load(path="x.csv")
        for_each(items=data, do=do_fn)
        _tracer.stop()
        dag = _build(_tracer.get_nodes())

        bp = dag.to_blueprint()
        fe_step = next(s for s in bp.steps if s.brick == "__for_each__")
        assert fe_step is not None

    def test_to_blueprint_branch_becomes_builtin(self) -> None:
        """branch node maps to __branch__ brick."""

        def true_fn() -> Node:
            """True branch."""
            return step.approve()

        def false_fn() -> Node:
            """False branch."""
            return step.reject()

        _tracer.start()
        branch("is_valid", if_true=true_fn, if_false=false_fn)
        _tracer.stop()
        dag = _build(_tracer.get_nodes())

        bp = dag.to_blueprint()
        br_step = next(s for s in bp.steps if s.brick == "__branch__")
        assert br_step.params["condition_brick"] == "is_valid"

    def test_to_blueprint_name_and_description(self) -> None:
        """Custom name and description flow through to BlueprintDefinition."""
        _tracer.start()
        step.noop()
        _tracer.stop()
        dag = _build(_tracer.get_nodes())

        bp = dag.to_blueprint(name="custom", description="my desc")
        assert bp.name == "custom"
        assert bp.description == "my desc"


class TestDAGAccessors:
    """Tests for DAG.get_node() and DAG.get_dependencies()."""

    def test_dag_get_node(self) -> None:
        """get_node returns the correct node."""
        n = Node(type="brick", brick_name="my_brick")
        dag = DAG(nodes={n.id: n}, edges={n.id: []})
        assert dag.get_node(n.id) is n

    def test_dag_get_dependencies(self) -> None:
        """get_dependencies returns the correct dependency nodes."""
        a = Node(type="brick", brick_name="a")
        b = Node(type="brick", brick_name="b")
        dag = DAG(
            nodes={a.id: a, b.id: b},
            edges={a.id: [], b.id: [a.id]},
        )
        deps = dag.get_dependencies(b.id)
        assert len(deps) == 1
        assert deps[0] is a
