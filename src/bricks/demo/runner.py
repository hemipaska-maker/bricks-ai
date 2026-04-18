"""DemoRunner: orchestrates the three-act Bricks demo."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from bricks.api import Bricks, _build_default_registry
from bricks.core.engine import BlueprintEngine
from bricks.core.loader import BlueprintLoader
from bricks.core.models import BlueprintDefinition
from bricks.core.registry import BrickRegistry
from bricks.demo import printer
from bricks.demo.data import (
    DEMO_BLUEPRINT_YAML,
    DEMO_LLM_PER_RUN_TOKENS,
    DEMO_TASK_TEXT,
    RAW_LLM_PROMPT_TEMPLATE,
    SAMPLE_CRM,
    SIMULATED_LLM_RESPONSES,
    DemoMetrics,
    generate_variants,
)

if TYPE_CHECKING:
    from bricks.llm.base import LLMProvider


class DemoRunner:
    """Orchestrates the three-act Bricks interactive demo.

    Acts:
        1. That was easy — compose a blueprint and execute it.
        2. It's always right — 5 cached Bricks runs vs 5 raw LLM runs.
        3. It's basically free — token cost comparison table.

    Args:
        provider: Optional LLM provider. If ``None``, runs in demo mode
            (pre-composed blueprints, simulated LLM responses).
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Initialise the runner.

        Args:
            provider: LLM provider for live mode. Pass ``None`` for demo mode.
        """
        self._provider = provider
        self._live = provider is not None
        self._metrics = DemoMetrics(live=self._live)
        self._blueprint: BlueprintDefinition | None = None
        self._registry: BrickRegistry = _build_default_registry()
        self._bricks_engine: Bricks | None = Bricks.default(provider=provider) if provider is not None else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> None:
        """Run all three acts in sequence."""
        printer.print_welcome()
        self.run_act1()
        printer.divider()
        self.run_act2()
        printer.divider()
        self.run_act3()

    def run_act1(self) -> None:
        """Act 1 — That was easy: compose and execute the CRM pipeline."""
        printer.act_header(1, "That was easy")
        printer.print_message("Task: Filter active customers from CRM data and sum their revenue")
        printer.print_message("")
        printer.show_customer_table(SAMPLE_CRM, "Sample CRM Data")

        if self._live and self._bricks_engine is not None:
            printer.print_mode("Running in LIVE mode")
            with printer.spinner("Composing blueprint via LLM..."):
                result = self._bricks_engine.execute(DEMO_TASK_TEXT, inputs={"customers": SAMPLE_CRM})
            self._metrics.compose_tokens = result["tokens_used"]
            revenue = float(result["outputs"]["total_active_revenue"])
        else:
            printer.print_mode("Running in DEMO mode (set BRICKS_MODEL or use --provider claudecode for live mode)")
            bp = self._get_blueprint()
            engine = BlueprintEngine(self._registry)
            with printer.spinner("Composing blueprint (pre-composed)..."):
                pass  # blueprint already loaded; spinner shows intent
            with printer.spinner("Executing..."):
                exec_result = engine.run(bp, inputs={"customers": SAMPLE_CRM})
            revenue = float(exec_result.outputs["total_active_revenue"])

        printer.show_yaml(DEMO_BLUEPRINT_YAML, "Blueprint YAML")
        printer.show_result("total_active_revenue", revenue)
        printer.print_message("Done. You described it in English. Bricks built and ran the pipeline.")

    def run_act2(self) -> None:
        """Act 2 — It's always right: Bricks consistency vs raw LLM accuracy."""
        printer.act_header(2, "It's always right")
        printer.print_message("Now let's test consistency. Same pipeline, 5 different datasets.")
        printer.print_message("")

        bp = self._get_blueprint()
        engine = BlueprintEngine(self._registry)
        variants = generate_variants()

        for i, (customers, expected) in enumerate(variants):
            bricks_value = self._run_bricks(i, customers, expected, bp, engine)
            llm_value = self._run_llm(i, customers)
            printer.show_run_result(
                n=i + 1,
                bricks_correct=abs(bricks_value - expected) < 0.01,
                bricks_value=bricks_value,
                llm_value=llm_value,
                expected=expected,
            )
            if abs(bricks_value - expected) < 0.01:
                self._metrics.bricks_correct += 1
            if llm_value is not None and abs(llm_value - expected) < 0.01:
                self._metrics.llm_correct += 1

        printer.print_message("")
        printer.print_message("Now let's see what a raw LLM does with the same data...")
        printer.print_summary_line(
            self._metrics.bricks_correct,
            self._metrics.llm_correct,
            self._metrics.num_variants,
        )

    def run_act3(self) -> None:
        """Act 3 — It's basically free: token cost comparison."""
        printer.act_header(3, "It's basically free")
        printer.print_message(f"Those {self._metrics.num_variants} Bricks runs? Here's what they cost:")
        printer.print_message("")
        printer.show_token_table(self._metrics)
        printer.print_message(
            "At scale (20 runs), Bricks saves 95%+ tokens. The blueprint is compiled once. After that, it's pure code."
        )
        printer.print_message("")
        printer.print_closing()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_blueprint(self) -> BlueprintDefinition:
        """Return the loaded demo blueprint, loading it if needed.

        Returns:
            The loaded :class:`~bricks.core.models.BlueprintDefinition`.
        """
        if self._blueprint is None:
            self._blueprint = BlueprintLoader().load_string(DEMO_BLUEPRINT_YAML)
        return self._blueprint

    def _run_bricks(
        self,
        idx: int,
        customers: list[dict[str, Any]],
        expected: float,
        bp: BlueprintDefinition,
        engine: BlueprintEngine,
    ) -> float:
        """Execute one variant through the Bricks pipeline.

        Args:
            idx: Variant index (0-based).
            customers: Customer list for this variant.
            expected: Expected active revenue (unused here, tracked by caller).
            bp: Pre-loaded blueprint for demo mode.
            engine: Pre-built engine for demo mode.

        Returns:
            The ``total_active_revenue`` output value.
        """
        if self._live and self._bricks_engine is not None:
            result = self._bricks_engine.execute(DEMO_TASK_TEXT, inputs={"customers": customers})
            self._metrics.bricks_run_tokens += result["tokens_used"]
            return float(result["outputs"]["total_active_revenue"])
        exec_result = engine.run(bp, inputs={"customers": customers})
        return float(exec_result.outputs["total_active_revenue"])

    def _run_llm(self, idx: int, customers: list[dict[str, Any]]) -> float | None:
        """Call the raw LLM for one variant (or return simulated value).

        Args:
            idx: Variant index (0-based); used to look up simulated responses.
            customers: Customer list for this variant.

        Returns:
            Parsed ``total_active_revenue`` float, or ``None`` on parse failure.
        """
        if self._live and self._provider is not None:
            prompt = RAW_LLM_PROMPT_TEMPLATE.format(data=json.dumps({"customers": customers}))
            response = self._provider.complete(prompt)
            self._metrics.llm_run_tokens += response.input_tokens + response.output_tokens
            try:
                return float(json.loads(response.text)["total_active_revenue"])
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                return None

        # Demo mode: use pre-written simulated responses
        self._metrics.llm_run_tokens += DEMO_LLM_PER_RUN_TOKENS
        return SIMULATED_LLM_RESPONSES[idx]
