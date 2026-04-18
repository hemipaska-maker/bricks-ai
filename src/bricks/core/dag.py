"""Bricks DAG — directed acyclic graph of DSL nodes.

Provides :class:`DAG` which stores a graph of :class:`~bricks.core.dsl.Node`
objects and can convert the graph into a :class:`~bricks.core.models.BlueprintDefinition`
that the existing engine can execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from bricks.core.dsl import Node

if TYPE_CHECKING:
    from bricks.core.models import BlueprintDefinition


def _resolve_param(value: Any, node_to_step_name: dict[str, str]) -> Any:
    """Recursively resolve Node references in param values to ``${step.result}`` strings.

    Handles direct Node values, as well as Nodes nested inside lists and dicts.
    If a Node's id is not in the mapping (shouldn't happen in normal DAG construction),
    the raw value is returned unchanged as a defensive fallback.

    Args:
        value: A param value — may be a Node, list, dict, or scalar.
        node_to_step_name: Mapping of node IDs to step names.

    Returns:
        The value with all resolvable Node references replaced by reference strings.
    """
    if isinstance(value, Node) and value.id in node_to_step_name:
        return f"${{{node_to_step_name[value.id]}.result}}"
    if isinstance(value, list):
        return [_resolve_param(v, node_to_step_name) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_param(v, node_to_step_name) for k, v in value.items()}
    return value


@dataclass
class DAG:
    """Directed acyclic graph of Bricks DSL nodes.

    Attributes:
        nodes: Mapping from node id to :class:`~bricks.core.dsl.Node`.
        edges: Mapping from node id to list of dependency node ids.
        root_id: Id of the final/return node.
    """

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)
    root_id: str = ""

    def topological_sort(self) -> list[str]:
        """Return node ids in execution order (dependencies before dependents).

        Uses Kahn's algorithm. Nodes at the same depth are sorted
        deterministically by id.

        Returns:
            Ordered list of node ids.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        in_degree: dict[str, int] = dict.fromkeys(self.nodes, 0)
        for nid, deps in self.edges.items():
            in_degree[nid] = len(deps)

        # Build reverse adjacency: dep_id → [nodes that depend on it]
        reverse: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for nid, deps in self.edges.items():
            for dep in deps:
                reverse[dep].append(nid)

        queue = sorted(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []

        while queue:
            nid = queue.pop(0)
            result.append(nid)
            for dependent in sorted(reverse[nid]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
            queue.sort()

        if len(result) != len(self.nodes):
            raise ValueError("DAG contains a cycle")

        return result

    def get_node(self, node_id: str) -> Node:
        """Get a node by id.

        Args:
            node_id: The node's unique identifier.

        Returns:
            The :class:`~bricks.core.dsl.Node` with that id.

        Raises:
            KeyError: If no node with that id exists.
        """
        return self.nodes[node_id]

    def get_dependencies(self, node_id: str) -> list[Node]:
        """Get all direct dependencies of a node.

        Args:
            node_id: The node's unique identifier.

        Returns:
            List of :class:`~bricks.core.dsl.Node` objects this node depends on.
        """
        return [self.nodes[dep_id] for dep_id in self.edges.get(node_id, [])]

    def to_blueprint(self, name: str = "dsl_pipeline", description: str = "") -> BlueprintDefinition:
        """Convert this DAG to a BlueprintDefinition for the existing engine.

        Maps each :class:`~bricks.core.dsl.Node` to a
        :class:`~bricks.core.models.StepDefinition`. Node references in
        ``params`` become ``${step_name.result}`` reference strings.
        ``for_each`` nodes map to the ``__for_each__`` built-in brick;
        ``branch`` nodes map to ``__branch__``.

        Args:
            name: Blueprint name. Defaults to ``"dsl_pipeline"``.
            description: Blueprint description. Auto-generated when empty.

        Returns:
            A :class:`~bricks.core.models.BlueprintDefinition` ready for the
            existing :class:`~bricks.core.engine.BlueprintEngine`.
        """
        from bricks.core.models import BlueprintDefinition, StepDefinition  # noqa: PLC0415

        ordered = self.topological_sort()
        steps: list[StepDefinition] = []
        node_to_step_name: dict[str, str] = {}

        for i, node_id in enumerate(ordered):
            node = self.nodes[node_id]
            step_name = f"step_{i + 1}_{node.brick_name or node.type}"
            node_to_step_name[node.id] = step_name
            step = self._node_to_step(node, step_name, node_to_step_name)
            steps.append(step)

        # Surface the terminal brick node's result via outputs_map so execute()
        # callers receive {"result": <value>} instead of an empty dict.
        # Only applies to plain brick nodes — for_each/branch manage their own output.
        outputs_map: dict[str, str] = {}
        root_node = self.nodes.get(self.root_id) if self.root_id else None
        if root_node is not None and root_node.type in ("brick", "for_each") and self.root_id in node_to_step_name:
            root_step = node_to_step_name[self.root_id]
            outputs_map = {"result": f"${{{root_step}.result}}"}

        return BlueprintDefinition(
            name=name,
            description=description or f"DSL-generated pipeline with {len(steps)} steps",
            steps=steps,
            outputs_map=outputs_map,
        )

    def _node_to_step(
        self,
        node: Node,
        step_name: str,
        node_to_step_name: dict[str, str],
    ) -> Any:
        """Convert a single Node to a StepDefinition.

        Args:
            node: The node to convert.
            step_name: Assigned name for this step.
            node_to_step_name: Mapping already-processed node ids to step names.

        Returns:
            A :class:`~bricks.core.models.StepDefinition`.
        """
        from bricks.core.models import StepDefinition  # noqa: PLC0415

        if node.type == "brick":
            resolved: dict[str, Any] = {}
            for key, value in node.params.items():
                resolved[key] = _resolve_param(value, node_to_step_name)
            return StepDefinition(name=step_name, brick=node.brick_name, params=resolved, save_as=step_name)

        if node.type == "for_each":
            items_ref: str = ""
            if isinstance(node.items, Node) and node.items.id in node_to_step_name:
                items_ref = f"${{{node_to_step_name[node.items.id]}.result}}"
            do_name = node.do if isinstance(node.do, str) else str(node.do)
            return StepDefinition(
                name=step_name,
                brick="__for_each__",
                params={"items": items_ref, "do_brick": do_name, "on_error": node.on_error},
                save_as=step_name,
            )

        # branch
        return StepDefinition(
            name=step_name,
            brick="__branch__",
            params={
                "condition_brick": node.condition,
                "if_true_brick": "",
                "if_false_brick": "",
            },
            save_as=step_name,
        )
