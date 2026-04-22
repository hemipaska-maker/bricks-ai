"""Built-in bricks for DSL control flow (__for_each__, __branch__).

These bricks are registered automatically when a ``DAGExecutionEngine`` is
used. They are hidden from user-facing catalog listings — any brick whose
name starts with ``__`` is excluded from ``list_public()`` and signature output.
"""

from __future__ import annotations

from typing import Any, Literal

from bricks.core.exceptions import BrickExecutionError
from bricks.core.models import BrickMeta
from bricks.core.registry import BrickRegistry


def _for_each_impl(
    items: list[Any],
    do_brick: str,
    on_error: Literal["fail", "collect"] = "fail",
    item_kwarg: str = "item",
    static_kwargs: dict[str, Any] | None = None,
    registry: BrickRegistry | None = None,
) -> dict[str, Any]:
    """Execute a brick for each item in the list.

    Args:
        items: List of items to iterate over.
        do_brick: Name of the brick to apply to each item.
        on_error: ``"fail"`` stops on first error; ``"collect"`` continues.
        item_kwarg: Keyword name to pass each item under. Extracted by the
            DSL tracer from the for_each lambda (e.g. ``"email"`` for
            ``for_each(do=lambda e: step.is_email_valid(email=e))``).
            Defaults to ``"item"`` for blueprints written without the DSL.
        static_kwargs: Literal keyword arguments the lambda closed over, to
            be passed on every iteration alongside ``item_kwarg`` — e.g.
            ``{"rename_map": {"id": "customer_id"}}`` for
            ``for_each(do=lambda r: step.rename_dict_keys(input=r, rename_map={...}))``.
            The per-item kwarg wins on name conflict.
        registry: Registry to look up ``do_brick``. Required.

    Returns:
        ``{"results": [...], "result": [...]}`` on success (fail mode).
        Also includes ``"errors": [...]`` in collect mode.

    Raises:
        ValueError: If ``registry`` is None.
        BrickExecutionError: Re-raised (in fail mode) for inner brick
            failures, attributed to the real inner brick name.
    """
    if registry is None:
        raise ValueError("__for_each__ requires a registry parameter.")

    callable_, _ = registry.get(do_brick)
    static: dict[str, Any] = dict(static_kwargs or {})
    results: list[Any] = []
    errors: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        try:
            # Merge statics first, then overlay the per-item kwarg so it wins
            # any name conflict (a lambda that closed over a key matching
            # ``item_kwarg`` would otherwise shadow the iterator).
            call_kwargs = {**static, item_kwarg: item}
            result = callable_(**call_kwargs)
        except BrickExecutionError:
            # Already attributed (e.g. nested for_each). Preserve it.
            if on_error != "collect":
                raise
            errors.append({"index": i, "error": f"{do_brick}: propagated", "item": item})
            results.append(None)
            continue
        except Exception as exc:
            # Attribute the failure to the real inner brick so healers,
            # logs, and traceback consumers see ``do_brick`` — not the
            # ``__for_each__`` wrapper. See issue #34.
            if on_error != "collect":
                raise BrickExecutionError(
                    brick_name=do_brick,
                    step_name=f"{do_brick}[item_{i}]",
                    cause=exc,
                ) from exc
            errors.append({"index": i, "error": f"{do_brick}: {exc}", "item": item})
            results.append(None)
            continue
        results.append(result)

    # Aliases ``result`` to the per-item list so chained steps that use the
    # DSL's ``<node>.output`` convention (resolved as ``${step.result}``)
    # find the list. ``results`` stays for callers that already consume it.
    output: dict[str, Any] = {"results": results, "result": results}
    if on_error == "collect":
        output["errors"] = errors
    return output


def _branch_impl(
    condition_brick: str,
    condition_input: Any = None,
    if_true_brick: str = "",
    if_false_brick: str = "",
    registry: BrickRegistry | None = None,
) -> dict[str, Any]:
    """Evaluate a condition brick and route to the true or false branch.

    Args:
        condition_brick: Brick name that returns a boolean or ``{"result": bool}``.
        condition_input: Input passed to the condition brick.
        if_true_brick: Brick to execute when condition is True.
        if_false_brick: Brick to execute when condition is False.
        registry: Registry to look up bricks. Required.

    Returns:
        Output of the executed branch plus ``{"branch_taken": "true"|"false"}``.

    Raises:
        ValueError: If ``registry`` is None.
    """
    if registry is None:
        raise ValueError("__branch__ requires a registry parameter.")

    def _invoke(brick: str, position: str) -> Any:
        """Invoke ``brick`` and attribute any failure to it (issue #34)."""
        fn, _ = registry.get(brick)
        try:
            return fn(input=condition_input)
        except BrickExecutionError:
            raise  # already attributed
        except Exception as exc:
            raise BrickExecutionError(
                brick_name=brick,
                step_name=f"{brick}[{position}]",
                cause=exc,
            ) from exc

    raw = _invoke(condition_brick, "condition")
    is_true = bool(raw.get("result", False) if isinstance(raw, dict) else raw)

    if is_true and if_true_brick:
        branch_result = _invoke(if_true_brick, "if_true")
        branch_taken = "true"
    elif if_false_brick:
        branch_result = _invoke(if_false_brick, "if_false")
        branch_taken = "false"
    else:
        branch_result = {}
        branch_taken = "false"

    output = dict(branch_result) if isinstance(branch_result, dict) else {"result": branch_result}
    output["branch_taken"] = branch_taken
    return output


def register_builtins(registry: BrickRegistry) -> None:
    """Register all built-in DSL bricks into *registry*.

    Each built-in is registered as a partial that closes over ``registry``,
    so the engine can call it without explicitly passing ``registry=``.

    Silently skips if they are already registered (idempotent).

    Args:
        registry: The registry to populate.
    """
    import functools  # noqa: PLC0415

    for name, fn, description in (
        ("__for_each__", _for_each_impl, "Internal: maps a brick over each item in a list."),
        ("__branch__", _branch_impl, "Internal: conditional routing based on a brick's boolean output."),
    ):
        if not registry.has(name):
            bound = functools.partial(fn, registry=registry)
            meta = BrickMeta(name=name, description=description, category="__builtin__")
            registry.register(name, bound, meta)
