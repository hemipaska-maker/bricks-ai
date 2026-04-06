"""RuntimeOrchestrator: single-call task executor.

Wires together: BrickSelector → BlueprintComposer → BlueprintEngine.
The store lookup is handled transparently by the composer (cache hit → 0 tokens).
"""

from __future__ import annotations

from typing import Any

from bricks.ai.composer import BlueprintComposer
from bricks.boot.config import SystemConfig
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import OrchestratorError
from bricks.core.loader import BlueprintLoader
from bricks.core.models import Verbosity
from bricks.core.registry import BrickRegistry
from bricks.core.selector import AllBricksSelector, BrickSelector
from bricks.llm.base import LLMProvider
from bricks.orchestrator.input_mapper import InputMapper
from bricks.selector.keyword_tier import KeywordTier
from bricks.selector.selector import TieredBrickSelector
from bricks.store.blueprint_store import BlueprintStore, FileBlueprintStore, MemoryBlueprintStore


def _build_selector(config: SystemConfig) -> BrickSelector:
    """Build a BrickSelector from config.

    Args:
        config: Resolved system configuration.

    Returns:
        ``TieredBrickSelector`` (Tier 1 keyword) if categories are configured,
        else ``AllBricksSelector``.
    """
    if config.brick_categories or config.tags:
        return TieredBrickSelector(
            tiers=[KeywordTier()],
            max_results=config.max_selector_results,
        )
    return AllBricksSelector()


def _build_store(config: SystemConfig) -> BlueprintStore | None:
    """Build a BlueprintStore from config.

    Args:
        config: Resolved system configuration.

    Returns:
        A configured store, or ``None`` if ``config.store.enabled`` is False.
    """
    if not config.store.enabled:
        return None
    if config.store.backend == "file":
        return FileBlueprintStore(config.store.path)
    return MemoryBlueprintStore()


class RuntimeOrchestrator:
    """Single-call task executor: compose → validate → execute.

    The store lookup and auto-save are handled transparently inside
    ``BlueprintComposer.compose()``. On a store cache hit, no LLM tokens
    are consumed and the pipeline runs directly.

    Args:
        config: Resolved system configuration from ``SystemBootstrapper``.
        registry: The brick registry to compose and execute against.
    """

    def __init__(
        self,
        config: SystemConfig,
        registry: BrickRegistry,
        provider: LLMProvider | None = None,
    ) -> None:
        """Initialise the orchestrator and wire all components.

        Args:
            config: Resolved system configuration.
            registry: Brick registry for selection, composition, and execution.
            provider: Optional custom LLM provider. When omitted, a
                ``LiteLLMProvider`` is created from ``config.model`` and
                ``config.api_key``.
        """
        from bricks.llm.litellm_provider import LiteLLMProvider  # noqa: PLC0415

        self._registry = registry
        selector = _build_selector(config)
        store = _build_store(config)
        resolved_provider = provider or LiteLLMProvider(model=config.model, api_key=config.api_key)
        self._composer = BlueprintComposer(
            provider=resolved_provider,
            selector=selector,
            store=store,
        )
        self._engine = BlueprintEngine(registry)
        self._loader = BlueprintLoader()

    def execute(
        self,
        task_text: str,
        inputs: dict[str, Any] | None = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Execute a task end-to-end and return the outputs.

        Flow:
        1. ``compose()`` — checks store, calls LLM if miss, validates YAML
        2. ``load_string()`` — parse YAML → ``BlueprintDefinition``
        3. ``engine.run()`` — deterministic step-by-step execution
        4. Return outputs plus telemetry fields

        Args:
            task_text: Natural language task description.
            inputs: Input values for ``${inputs.X}`` references in the blueprint.
                    Defaults to an empty dict.
            verbose: When True, include blueprint YAML, step trace, model, and
                     timing in the result.

        Returns:
            A dict with keys:

            - ``outputs``: the blueprint's final ``outputs_map`` values
            - ``cache_hit``: ``True`` when the blueprint came from the store
            - ``api_calls``: number of LLM calls made (0 on cache hit)
            - ``tokens_used``: total tokens consumed
            - ``input_tokens``: LLM input tokens consumed
            - ``output_tokens``: LLM output tokens consumed
            - (verbose only) ``blueprint_yaml``, ``blueprint_name``, ``model``,
              ``compose_duration_seconds``, ``execution_duration_ms``, ``steps``

        Raises:
            OrchestratorError: If composition fails (YAML invalid after retries)
                or if blueprint execution raises an error.
        """
        compose_result = self._composer.compose(
            task_text,
            self._registry,
            input_keys=list((inputs or {}).keys()) or None,
        )
        if not compose_result.is_valid:
            errors = "; ".join(compose_result.validation_errors)
            raise OrchestratorError(f"Composition failed for task {task_text!r}: {errors}")
        try:
            blueprint = self._loader.load_string(compose_result.blueprint_yaml)
        except Exception as exc:
            raise OrchestratorError(f"Blueprint load error for task {task_text!r}: {exc}") from exc
        try:
            # Auto-map user input keys to blueprint variable names
            blueprint_input_vars = list(blueprint.inputs.keys()) if blueprint.inputs else []
            mapped = InputMapper().map(inputs or {}, blueprint_input_vars)
            verbosity = Verbosity.FULL if verbose else Verbosity.MINIMAL
            execution = self._engine.run(blueprint, mapped, verbosity=verbosity)
        except Exception as exc:
            raise OrchestratorError(f"Blueprint execution failed for task {task_text!r}: {exc}") from exc
        result: dict[str, Any] = {
            "outputs": execution.outputs,
            "cache_hit": compose_result.cache_hit,
            "api_calls": compose_result.api_calls,
            "tokens_used": compose_result.total_tokens,
            "input_tokens": compose_result.total_input_tokens,
            "output_tokens": compose_result.total_output_tokens,
        }
        if verbose:
            result["blueprint_yaml"] = compose_result.blueprint_yaml
            result["blueprint_name"] = execution.blueprint_name
            result["model"] = compose_result.model
            result["compose_duration_seconds"] = compose_result.duration_seconds
            result["execution_duration_ms"] = execution.total_duration_ms
            result["steps"] = [
                {
                    "step": s.step_name,
                    "brick": s.brick_name,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                    "duration_ms": s.duration_ms,
                }
                for s in execution.steps
            ]
        return result
