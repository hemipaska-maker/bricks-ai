"""End-to-end integration tests for the full DSL pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from bricks.ai.composer import BlueprintComposer
from bricks.core.builtins import register_builtins
from bricks.core.dsl import FlowDefinition, flow, for_each, step
from bricks.core.engine import BlueprintEngine, DAGExecutionEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.models import BrickMeta, ExecutionResult
from bricks.core.registry import BrickRegistry
from bricks.llm.base import CompletionResult, LLMProvider

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SIMPLE_DSL = """\
@flow
def add_numbers():
    result = step.add(a=3.0, b=4.0)
    return result
"""

_INVALID_DSL = """\
import os

@flow
def bad():
    return step.add(a=1.0, b=2.0)
"""


def _make_math_registry() -> BrickRegistry:
    """Registry with add and multiply bricks."""
    reg = BrickRegistry()

    def add(a: float, b: float) -> dict[str, Any]:
        """Add two numbers."""
        return {"result": a + b}

    def multiply(a: float, b: float) -> dict[str, Any]:
        """Multiply two numbers."""
        return {"result": a * b}

    for fn in (add, multiply):
        reg.register(fn.__name__, fn, BrickMeta(name=fn.__name__, description=fn.__doc__ or ""))
    return reg


def _make_composer(registry: BrickRegistry, response: str = _SIMPLE_DSL) -> BlueprintComposer:
    """Create a mocked composer."""
    composer = BlueprintComposer.__new__(BlueprintComposer)
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.complete.return_value = CompletionResult(text=response, input_tokens=5, output_tokens=10)
    composer._provider = mock_provider
    from bricks.core.selector import AllBricksSelector

    composer._selector = AllBricksSelector()
    composer._store = None
    composer._explicit_healers = None
    composer._pm = None
    return composer


# ---------------------------------------------------------------------------
# 1. Full pipeline: compose → validate DSL → exec
# ---------------------------------------------------------------------------


def test_full_pipeline_compose_and_execute() -> None:
    """Compose a task via mocked LLM, validate DSL, execute through engine, get results."""
    reg = _make_math_registry()
    engine = DAGExecutionEngine(BlueprintEngine(reg))
    composer = _make_composer(reg)

    compose_result = composer.compose("Add 3 + 4", reg)
    assert compose_result.is_valid

    # Execute the flow definition
    flow_def = composer._parse_dsl_response(_SIMPLE_DSL)
    result = engine.execute(flow_def)
    assert isinstance(result, ExecutionResult)


# ---------------------------------------------------------------------------
# 2. MCP: verbose response includes dsl_code
# ---------------------------------------------------------------------------


def test_mcp_execute_returns_dsl_code_when_verbose() -> None:
    """Orchestrator verbose result includes dsl_code field."""
    from bricks.orchestrator.runtime import RuntimeOrchestrator

    reg = _make_math_registry()
    composer = _make_composer(reg)
    be = BlueprintEngine(reg)
    orchestrator = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
    orchestrator._composer = composer
    orchestrator._registry = reg
    orchestrator._engine = be
    orchestrator._loader = BlueprintLoader()

    result = orchestrator.execute("Add numbers", verbose=True)
    assert "dsl_code" in result
    assert "@flow" in result["dsl_code"]


# ---------------------------------------------------------------------------
# 3. Catalog excludes builtins
# ---------------------------------------------------------------------------


def test_mcp_catalog_excludes_builtins() -> None:
    """bricks://catalog (via list_public) does not include __for_each__ or __branch__."""
    reg = _make_math_registry()
    register_builtins(reg)

    public_names = {name for name, _ in reg.list_public()}
    assert "__for_each__" not in public_names
    assert "__branch__" not in public_names
    assert "add" in public_names


# ---------------------------------------------------------------------------
# 4. CompositionError surfaces through MCP handler
# ---------------------------------------------------------------------------


def test_compose_error_surfaces_through_mcp() -> None:
    """DSL validation failure raises CompositionError with code in message."""
    reg = _make_math_registry()
    composer = _make_composer(reg, response=_INVALID_DSL)
    # Force both retries to return invalid code
    composer._provider.complete.return_value = CompletionResult(text=_INVALID_DSL)

    compose_result = composer.compose("bad task", reg)
    assert not compose_result.is_valid
    assert any("Import" in e or "import" in e for e in compose_result.validation_errors)


# ---------------------------------------------------------------------------
# 5. CRM DSL example structure
# ---------------------------------------------------------------------------


def test_dsl_example_crm_pipeline_runs() -> None:
    """The CRM pipeline DSL example produces a valid FlowDefinition."""
    from bricks.core.models import BlueprintDefinition

    @flow
    def crm_pipeline(records: Any) -> Any:
        """Clean CRM records, score them, and aggregate."""
        normalized = for_each(records, do=lambda r: step.normalize_contact(record=r))
        scored = for_each(normalized, do=lambda r: step.score_contact(record=r))
        return step.aggregate_contacts(results=scored)

    assert isinstance(crm_pipeline, FlowDefinition)
    bp = crm_pipeline.to_blueprint()
    assert isinstance(bp, BlueprintDefinition)
    assert crm_pipeline.name == "crm_pipeline"


# ---------------------------------------------------------------------------
# 6. Basics DSL example structure
# ---------------------------------------------------------------------------


def test_dsl_example_basics_runs() -> None:
    """The basics DSL example produces a valid FlowDefinition."""
    from bricks.core.models import BlueprintDefinition

    @flow
    def simple_chain() -> Any:
        """A simple two-step pipeline."""
        a = step.add(a=1.0, b=2.0)
        return step.multiply(a=a, b=3.0)

    assert isinstance(simple_chain, FlowDefinition)
    bp = simple_chain.to_blueprint()
    assert isinstance(bp, BlueprintDefinition)
    assert len(bp.steps) == 2


# ---------------------------------------------------------------------------
# 7. to_yaml() round-trips through BlueprintLoader
# ---------------------------------------------------------------------------


def test_flow_to_yaml_round_trips() -> None:
    """to_yaml() output can be loaded by BlueprintLoader."""

    @flow
    def add_flow() -> Any:
        return step.add(a=1.0, b=2.0)

    yaml_str = add_flow.to_yaml()
    assert yaml_str.strip() != ""

    loader = BlueprintLoader()
    bp = loader.load_string(yaml_str)
    assert bp.name == "add_flow"


# ---------------------------------------------------------------------------
# 8. Verbose response has both dsl_code and blueprint_yaml
# ---------------------------------------------------------------------------


def test_verbose_output_has_dsl_and_yaml() -> None:
    """Both dsl_code and blueprint_yaml present in verbose orchestrator response."""
    from bricks.orchestrator.runtime import RuntimeOrchestrator

    reg = _make_math_registry()
    composer = _make_composer(reg)
    be = BlueprintEngine(reg)
    orchestrator = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
    orchestrator._composer = composer
    orchestrator._registry = reg
    orchestrator._engine = be
    orchestrator._loader = BlueprintLoader()

    result = orchestrator.execute("Add numbers", verbose=True)
    assert "dsl_code" in result
    assert "blueprint_yaml" in result
    assert result["dsl_code"] != ""
    assert result["blueprint_yaml"] != ""
