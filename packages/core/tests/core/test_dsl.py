"""Tests for bricks.core.dsl — Node and StepProxy data model."""

from __future__ import annotations

import re

import pytest
from bricks.core.dsl import Node, StepProxy, step


class TestStepProxy:
    """Tests for StepProxy and the module-level step singleton."""

    def test_step_proxy_creates_brick_node(self) -> None:
        """step.clean(text='hi') returns Node with correct type, brick_name, params."""
        node = step.clean(text="hi")
        assert node.type == "brick"
        assert node.brick_name == "clean"
        assert node.params == {"text": "hi"}

    def test_step_proxy_different_bricks(self) -> None:
        """step.filter and step.sort create nodes with distinct brick_names."""
        n1 = step.filter(items=[], key="status", value="active")
        n2 = step.sort(items=[], field="name")
        assert n1.brick_name == "filter"
        assert n2.brick_name == "sort"
        assert n1.brick_name != n2.brick_name

    def test_step_proxy_no_positional_args(self) -> None:
        """step.clean('hello') raises TypeError — keyword-only."""
        with pytest.raises(TypeError):
            step.clean("hello")  # type: ignore[call-arg]

    def test_step_proxy_returns_callable(self) -> None:
        """Accessing step.X returns a callable before being called."""
        fn = step.my_brick
        assert callable(fn)

    def test_step_singleton_is_step_proxy(self) -> None:
        """The module-level step is a StepProxy instance."""
        assert isinstance(step, StepProxy)


class TestNode:
    """Tests for the Node dataclass."""

    def test_node_auto_generates_unique_id(self) -> None:
        """Two independently created nodes have different ids."""
        n1 = Node()
        n2 = Node()
        assert n1.id != n2.id

    def test_node_id_is_8_char_hex(self) -> None:
        """Node id is exactly 8 lowercase hex characters."""
        node = Node()
        assert re.fullmatch(r"[0-9a-f]{8}", node.id)

    def test_node_defaults(self) -> None:
        """Fresh Node() has expected default field values."""
        node = Node()
        assert node.type == ""
        assert node.brick_name == ""
        assert node.params == {}
        assert node.depends_on == []
        assert node.items is None
        assert node.do is None
        assert node.condition is None
        assert node.if_true is None
        assert node.if_false is None

    def test_node_on_error_default_is_fail(self) -> None:
        """Node.on_error defaults to 'fail'."""
        node = Node()
        assert node.on_error == "fail"

    def test_node_params_can_reference_other_nodes(self) -> None:
        """step.process(data=step.clean(text='x')) creates nested Node references."""
        inner = step.clean(text="x")
        outer = step.process(data=inner)
        assert isinstance(outer.params["data"], Node)
        assert outer.params["data"].brick_name == "clean"

    def test_node_repr_brick(self) -> None:
        """repr for a brick node shows brick_name and id."""
        node = Node(type="brick", brick_name="my_brick")
        r = repr(node)
        assert "brick='my_brick'" in r
        assert node.id in r

    def test_node_repr_non_brick(self) -> None:
        """repr for a non-brick node shows type and id."""
        node = Node(type="for_each")
        r = repr(node)
        assert "type='for_each'" in r
        assert node.id in r

    def test_node_for_each_fields(self) -> None:
        """Node stores for_each-specific fields correctly."""

        def do_fn(n: Node) -> Node:
            """Dummy for_each body."""
            return step.clean(text=n)

        items_node = step.load(path="data.csv")
        node = Node(type="for_each", items=items_node, do=do_fn, on_error="collect")
        assert node.items is items_node
        assert node.do is do_fn
        assert node.on_error == "collect"

    def test_node_branch_fields(self) -> None:
        """Node stores branch-specific fields correctly."""

        def true_fn() -> Node:
            """Dummy true branch."""
            return step.approve()

        def false_fn() -> Node:
            """Dummy false branch."""
            return step.reject()

        node = Node(type="branch", condition="is_valid", if_true=true_fn, if_false=false_fn)
        assert node.condition == "is_valid"
        assert node.if_true is true_fn
        assert node.if_false is false_fn

    def test_node_depends_on_is_mutable_list(self) -> None:
        """depends_on starts empty and can be appended to without aliasing."""
        n1 = Node()
        n2 = Node()
        n1.depends_on.append("abc")
        assert n2.depends_on == []  # no shared state


class TestImports:
    """Tests that public exports work as documented."""

    def test_import_from_bricks(self) -> None:
        """from bricks import step, Node works."""
        from bricks import Node as BricksNode
        from bricks import step as bricks_step

        assert bricks_step is not None
        assert BricksNode is Node

    def test_import_from_bricks_core_dsl(self) -> None:
        """from bricks.core.dsl import Node, StepProxy, step works."""
        from bricks.core.dsl import Node as BricksNode
        from bricks.core.dsl import StepProxy as BricksStepProxy
        from bricks.core.dsl import step as bricks_step

        assert isinstance(bricks_step, BricksStepProxy)
        assert BricksNode is Node
