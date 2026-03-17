"""BlueprintEngine: loads and executes YAML blueprints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from bricks.core.brick import BaseBrick, BrickModel
from bricks.core.context import ExecutionContext
from bricks.core.exceptions import BrickExecutionError
from bricks.core.models import (
    BlueprintDefinition,
    BrickMeta,
    ExecutionResult,
    StepResult,
    Verbosity,
)
from bricks.core.registry import BrickRegistry
from bricks.core.resolver import ReferenceResolver


def _call_teardown(
    callable_: Any,
    resolved_params: dict[str, Any],
    meta: BrickMeta,
    error: Exception,
) -> None:
    """Call teardown on a brick (class-based or function-based), suppressing exceptions.

    Args:
        callable_: The brick callable.
        resolved_params: The resolved parameter dict passed to the brick.
        meta: Brick metadata.
        error: The original execution error.
    """
    try:
        if isinstance(callable_, BaseBrick):
            callable_.teardown(BrickModel(), meta, error)
        elif hasattr(callable_, "__brick_teardown__") and callable_.__brick_teardown__ is not None:
            callable_.__brick_teardown__(resolved_params, error)
    except Exception:  # noqa: S110
        pass  # Never mask the original error


class BlueprintEngine:
    """Executes a validated BlueprintDefinition step-by-step.

    Each step resolves its parameter references, looks up the brick
    in the registry, executes it, and optionally saves the result.

    Steps may reference a ``brick`` (registered callable) or a ``blueprint``
    (path to a child YAML file), enabling sub-blueprint composition.

    On failure, teardown is called on the failing step, then in reverse
    order on all previously completed steps, before re-raising.

    The ``verbosity`` parameter controls how much execution detail is included
    in the returned :class:`~bricks.core.models.ExecutionResult`:

    - ``MINIMAL`` (default): final ``outputs`` only.
    - ``STANDARD``: ``outputs`` + per-step output dicts.
    - ``FULL``: ``outputs`` + per-step inputs/outputs/timing + total duration.
    """

    _MAX_DEPTH: int = 10

    def __init__(self, registry: BrickRegistry, loader: Any | None = None) -> None:
        """Initialise the engine.

        Args:
            registry: The brick registry to use for step execution.
            loader: Optional BlueprintLoader. Defaults to a new BlueprintLoader instance.
        """
        from bricks.core.loader import BlueprintLoader  # noqa: PLC0415 — avoid circular at module level

        self._registry = registry
        self._loader: BlueprintLoader = loader if loader is not None else BlueprintLoader()
        self._resolver = ReferenceResolver()

    def run(
        self,
        blueprint: BlueprintDefinition,
        inputs: dict[str, Any] | None = None,
        verbosity: Verbosity = Verbosity.MINIMAL,
    ) -> ExecutionResult:
        """Execute a blueprint and return a structured result.

        Args:
            blueprint: A validated BlueprintDefinition.
            inputs: Runtime input values matching the blueprint's input schema.
            verbosity: Controls execution trace detail in the returned result.

        Returns:
            An :class:`~bricks.core.models.ExecutionResult` with ``outputs``
            always populated. ``steps`` and timing fields populated according
            to ``verbosity``.

        Raises:
            BrickExecutionError: If any step fails during execution.
        """
        return self._execute(blueprint, inputs, depth=0, verbosity=verbosity)

    def _execute(
        self,
        blueprint: BlueprintDefinition,
        inputs: dict[str, Any] | None,
        depth: int,
        verbosity: Verbosity = Verbosity.MINIMAL,
    ) -> ExecutionResult:
        """Internal recursive execution helper.

        Args:
            blueprint: The blueprint to execute.
            inputs: Runtime inputs.
            depth: Current recursion depth (0 = top level).
            verbosity: Execution trace detail level.

        Returns:
            An ExecutionResult.

        Raises:
            BrickExecutionError: On step failure or recursion depth exceeded.
        """
        if depth > self._MAX_DEPTH:
            raise BrickExecutionError(
                brick_name="<sub-blueprint>",
                step_name="<depth-check>",
                cause=RecursionError(f"Sub-blueprint recursion depth exceeded (max {self._MAX_DEPTH})"),
            )

        context = ExecutionContext(inputs=inputs)
        completed: list[tuple[Any, dict[str, Any], BrickMeta]] = []
        step_results: list[StepResult] = []
        total_start = time.perf_counter()

        for step in blueprint.steps:
            resolved_params = self._resolver.resolve(step.params, context)

            if step.brick is not None:
                # ── Function/class-based brick ─────────────────────────────
                callable_, meta = self._registry.get(step.brick)

                t0 = time.perf_counter()
                try:
                    result = callable_(**resolved_params)
                except Exception as exc:
                    _call_teardown(callable_, resolved_params, meta, exc)
                    for prev_callable, prev_params, prev_meta in reversed(completed):
                        _call_teardown(prev_callable, prev_params, prev_meta, exc)
                    raise BrickExecutionError(
                        brick_name=step.brick,
                        step_name=step.name,
                        cause=exc,
                    ) from exc

                duration_ms = (time.perf_counter() - t0) * 1000
                completed.append((callable_, resolved_params, meta))

                if verbosity in (Verbosity.STANDARD, Verbosity.FULL):
                    step_results.append(
                        StepResult(
                            step_name=step.name,
                            brick_name=step.brick,
                            inputs=resolved_params if verbosity == Verbosity.FULL else {},
                            outputs=result if isinstance(result, dict) else {},
                            duration_ms=duration_ms if verbosity == Verbosity.FULL else 0.0,
                            save_as=step.save_as,
                        )
                    )

            else:
                # ── Sub-blueprint ──────────────────────────────────────────
                # step.blueprint is not None here (guaranteed by model validator)
                child_path = Path(step.blueprint or "")
                try:
                    child_bp = self._loader.load_file(child_path)
                    child_result = self._execute(child_bp, resolved_params, depth + 1, verbosity)
                    result = child_result.outputs
                except BrickExecutionError:
                    raise
                except Exception as exc:
                    raise BrickExecutionError(
                        brick_name=step.blueprint or "<sub-blueprint>",
                        step_name=step.name,
                        cause=exc,
                    ) from exc

                if verbosity in (Verbosity.STANDARD, Verbosity.FULL):
                    step_results.append(
                        StepResult(
                            step_name=step.name,
                            brick_name=step.blueprint or "<sub-blueprint>",
                            inputs=resolved_params if verbosity == Verbosity.FULL else {},
                            outputs=result if isinstance(result, dict) else {},
                            save_as=step.save_as,
                        )
                    )

            if step.save_as is not None:
                context.save_result(step.save_as, result)
            context.advance_step()

        outputs: dict[str, Any] = self._resolver.resolve(blueprint.outputs_map, context)
        total_ms = (time.perf_counter() - total_start) * 1000

        return ExecutionResult(
            outputs=outputs,
            steps=step_results,
            total_duration_ms=total_ms if verbosity == Verbosity.FULL else 0.0,
            blueprint_name=blueprint.name,
            verbosity=verbosity,
        )
