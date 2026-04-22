"""Public Python API for Bricks — thin wrapper over SystemBootstrapper + RuntimeOrchestrator.

Usage::

    from bricks import Bricks

    # Boot from structured YAML config (no LLM call)
    engine = Bricks.from_config("agent.yaml")

    # Boot from a markdown skill description (one LLM call)
    engine = Bricks.from_skill("skill.md", api_key="sk-ant-...")

    # Execute a task
    result = engine.execute(
        task="filter active customers and calculate total revenue",
        inputs={"api_response": raw_data},
    )
    print(result)  # {"outputs": {...}, "cache_hit": False, "api_calls": 1, "tokens_used": 1234}
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from bricks.boot.bootstrapper import SystemBootstrapper
from bricks.core.registry import BrickRegistry
from bricks.orchestrator.runtime import RuntimeOrchestrator

if TYPE_CHECKING:
    from bricks.llm.base import LLMProvider
    from bricks.store.blueprint_store import BlueprintStore

_DEFAULT_MODEL: str = "claude-haiku-4-5-20251001"


def _build_default_registry() -> BrickRegistry:
    """Build the default registry by discovering installed brick packs.

    Also registers DSL control-flow builtins (``__for_each__`` / ``__branch__``).
    Without this, any composed blueprint that wraps iteration in ``for_each``
    fails at execute() with ``BrickNotFoundError: '__for_each__'`` —
    issue #66 bug B.

    Returns:
        A :class:`~bricks.core.registry.BrickRegistry` populated with all
        bricks from every installed pack plus DSL builtins.

    Raises:
        BricksConfigError: If no packs (e.g. ``bricks-stdlib``) are installed.
    """
    from bricks.core.builtins import register_builtins  # noqa: PLC0415
    from bricks.packs import discover_and_load  # noqa: PLC0415

    reg = BrickRegistry()
    discover_and_load(reg)
    register_builtins(reg)
    return reg


class Bricks:
    """Public Python entry point for the Bricks execution engine.

    Wraps :class:`~bricks.boot.bootstrapper.SystemBootstrapper` and
    :class:`~bricks.orchestrator.runtime.RuntimeOrchestrator` behind two class
    methods and one execute method.  No logic lives here — it is a thin facade.

    Example::

        engine = Bricks.from_config("agent.yaml")
        result = engine.execute("sum all revenue values", inputs={"values": [1, 2, 3]})
    """

    def __init__(self, orchestrator: RuntimeOrchestrator) -> None:
        """Initialise with a pre-built orchestrator.

        Args:
            orchestrator: Fully configured runtime orchestrator.
        """
        self._orchestrator = orchestrator

    # ── class-method constructors ────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        *,
        api_key: str = "",
        registry: BrickRegistry | None = None,
    ) -> Bricks:
        """Boot from a structured YAML config file (no LLM call).

        Args:
            config_path: Path to an ``agent.yaml`` or ``agent.yml`` file.
            api_key: Anthropic API key used for task composition (not for boot).
                Overrides the key in the config file if provided.
            registry: Optional custom brick registry.  Defaults to all
                bricks from installed packs (see ``pip install bricks-stdlib``).

        Returns:
            A ready-to-use :class:`Bricks` instance.

        Raises:
            FileNotFoundError: If ``config_path`` does not exist.
            ValueError: If the file extension is not ``.yaml`` or ``.yml``.
        """
        bootstrapper = SystemBootstrapper(api_key=api_key)
        config = bootstrapper.bootstrap(Path(config_path))
        # api_key kwarg overrides whatever is in the config file
        if api_key:
            config = config.model_copy(update={"api_key": api_key})
        reg = registry if registry is not None else _build_default_registry()
        return cls(RuntimeOrchestrator(config, reg))

    @classmethod
    def from_skill(
        cls,
        skill_path: str | Path,
        *,
        api_key: str = "",
        model: str = _DEFAULT_MODEL,
        registry: BrickRegistry | None = None,
    ) -> Bricks:
        """Boot from a markdown skill description (one LLM call to extract domain).

        Args:
            skill_path: Path to a ``skill.md`` markdown file describing the agent.
            api_key: Anthropic API key — used both to extract domain keywords
                during boot and for subsequent task composition.
            model: Claude model for the boot LLM call.
            registry: Optional custom brick registry.  Defaults to all
                bricks from installed packs (see ``pip install bricks-stdlib``).

        Returns:
            A ready-to-use :class:`Bricks` instance.

        Raises:
            FileNotFoundError: If ``skill_path`` does not exist.
            ValueError: If the file extension is not ``.md``.
        """
        bootstrapper = SystemBootstrapper(api_key=api_key, model=model)
        config = bootstrapper.bootstrap(Path(skill_path))
        if api_key:
            config = config.model_copy(update={"api_key": api_key})
        reg = registry if registry is not None else _build_default_registry()
        return cls(RuntimeOrchestrator(config, reg))

    @classmethod
    def default(
        cls,
        *,
        model: str | None = None,
        api_key: str = "",
        provider: LLMProvider | None = None,
        store_backend: str = "memory",
        store_path: str = "",
    ) -> Bricks:
        """Zero-config entry point — no config file needed.

        Args:
            model: LiteLLM model string. Overrides ``BRICKS_MODEL`` env var.
                Defaults to ``claude-haiku-4-5``.
            api_key: Explicit API key. Leave empty to read from environment.
            provider: Custom LLM provider. When supplied, ``model`` and
                ``api_key`` are ignored for LLM calls.
            store_backend: Blueprint store backend — ``"memory"`` (session-scoped,
                default) or ``"file"`` (persistent across restarts).
            store_path: Directory for the file backend. Ignored for memory backend.
                Tilde expansion is applied automatically.

        Returns:
            A ready-to-use :class:`Bricks` instance backed by all stdlib bricks.

        Raises:
            BricksConfigError: If no API key is found when the first task is executed.
        """
        import os  # noqa: PLC0415

        from bricks.boot.config import SystemConfig  # noqa: PLC0415
        from bricks.core.config import StoreConfig  # noqa: PLC0415
        from bricks.llm.litellm_provider import LiteLLMProvider  # noqa: PLC0415

        resolved_model = model or os.environ.get("BRICKS_MODEL", "claude-haiku-4-5")
        resolved_provider = provider or LiteLLMProvider(model=resolved_model, api_key=api_key)
        resolved_path = str(Path(store_path).expanduser()) if store_path else store_path
        store_config = StoreConfig(enabled=True, backend=store_backend, path=resolved_path)
        config = SystemConfig(name="default", model=resolved_model, api_key=api_key, store=store_config)
        reg = _build_default_registry()
        return cls(RuntimeOrchestrator(config, reg, provider=resolved_provider))

    # ── execution ────────────────────────────────────────────────────────────

    def execute(
        self,
        task: str,
        inputs: dict[str, Any] | None = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Execute a natural-language task end-to-end.

        Delegates directly to :meth:`RuntimeOrchestrator.execute`.

        Args:
            task: Natural language description of what to compute.
            inputs: Optional dict of input values for ``${inputs.X}``
                references in the generated blueprint.
            verbose: When True, include blueprint YAML, step trace, model, and
                timing in the result.

        Returns:
            dict with keys:

            - ``outputs`` — the blueprint's final output values
            - ``cache_hit`` — True if the blueprint was served from store
            - ``api_calls`` — number of LLM calls made (0 on cache hit)
            - ``tokens_used`` — total tokens consumed
            - ``input_tokens`` — LLM input tokens consumed
            - ``output_tokens`` — LLM output tokens consumed

        Raises:
            OrchestratorError: If composition or execution fails.
        """
        return self._orchestrator.execute(task, inputs, verbose=verbose)

    # ── read-only property accessors ────────────────────────────────────────

    @property
    def registry(self) -> BrickRegistry:
        """Return the brick registry backing this instance.

        Returns:
            The :class:`~bricks.core.registry.BrickRegistry` used for
            brick selection, composition, and execution.
        """
        return self._orchestrator._registry

    @property
    def blueprint_store(self) -> BlueprintStore | None:
        """Return the blueprint store, or None if no store is configured.

        Returns:
            The active :class:`~bricks.store.blueprint_store.BlueprintStore`,
            or ``None`` when the store is disabled.
        """
        return self._orchestrator._composer._store
