"""Pluggable engine interface for the CRM benchmark.

Both BricksEngine and RawLLMEngine receive identical input
(task_text + raw_data) and return identical EngineResult.
Only the system under test changes — same checker, same result format.

This follows controlled benchmarking methodology (MLPerf / HumanEval / HELM):
one variable at a time, nothing else changes.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EngineResult:
    """Output from one engine solving one task.

    Both BricksEngine and RawLLMEngine return this identical shape.
    """

    outputs: dict[str, Any]
    """Parsed structured outputs (e.g. {'active_count': 18, 'total_active_revenue': 3447.50})."""
    tokens_in: int
    """Input tokens consumed (real from API or estimated)."""
    tokens_out: int
    """Output tokens produced (real from API or estimated)."""
    duration_seconds: float
    """Wall-clock time for this call."""
    model: str
    """Model identifier string."""
    raw_response: str = ""
    """Full LLM text response (blueprint YAML for Bricks, JSON text for RawLLM)."""
    error: str = ""
    """Non-empty if the engine failed to produce valid outputs."""


@dataclass
class BenchmarkResult:
    """One engine's result on one task, evaluated against expected outputs."""

    engine_name: str
    """Class name of the engine (e.g. 'BricksEngine', 'RawLLMEngine')."""
    outputs: dict[str, Any]
    """Actual outputs returned by the engine."""
    expected: dict[str, Any]
    """Expected outputs from the task generator."""
    correct: bool
    """True if outputs match expected within float tolerance."""
    tokens_in: int
    tokens_out: int
    duration_seconds: float
    model: str
    raw_response: str = ""
    error: str = ""


class Engine(ABC):
    """Pluggable solver: swap only the system under test.

    Both implementations receive the same inputs and return the same output
    shape, so the benchmark can compare them with a single checker.
    """

    @abstractmethod
    def solve(self, task_text: str, raw_data: str) -> EngineResult:
        """Given task description and raw data, return structured outputs.

        Args:
            task_text: Natural language task description.
            raw_data: Raw data string (e.g. JSON API response).

        Returns:
            EngineResult with parsed outputs dict and metadata.
        """
        ...


class BricksEngine(Engine):
    """Compose a YAML blueprint from task_text, execute deterministically with raw_data.

    Pipeline: compose(task_text) → load(YAML) → execute(raw_data) → dict outputs.
    The LLM only sees brick signatures during compose, not the raw data.
    """

    def __init__(self, provider: Any) -> None:
        """Initialise with an LLMProvider.

        Args:
            provider: Any LLMProvider instance (LiteLLMProvider or ClaudeCodeProvider).
        """
        from bricks.ai.composer import BlueprintComposer
        from bricks.core.engine import BlueprintEngine
        from bricks.core.loader import BlueprintLoader
        from bricks.core.registry import BrickRegistry
        from bricks_stdlib import register as _register_stdlib  # type: ignore[import-untyped]

        self._composer = BlueprintComposer(provider=provider)
        self._loader = BlueprintLoader()
        registry = BrickRegistry()
        _register_stdlib(registry)
        self._registry = registry
        self._engine = BlueprintEngine(registry=registry)

    def solve(self, task_text: str, raw_data: str) -> EngineResult:
        """Compose blueprint from task_text, execute it with raw_data.

        Args:
            task_text: Natural language task description (used for compose).
            raw_data: Raw API response data (passed as blueprint input).

        Returns:
            EngineResult with blueprint execution outputs.
        """
        t0 = time.monotonic()
        compose_result = self._composer.compose(
            task_text, self._registry, input_keys=["raw_api_response"]
        )

        if not compose_result.is_valid:
            logger.error("[BricksEngine] Compose failed: %s", compose_result.validation_errors)
            return EngineResult(
                outputs={},
                tokens_in=compose_result.total_input_tokens,
                tokens_out=compose_result.total_output_tokens,
                duration_seconds=time.monotonic() - t0,
                model=compose_result.model,
                raw_response=compose_result.blueprint_yaml,
                error="; ".join(compose_result.validation_errors),
            )

        try:
            bp_def = self._loader.load_string(compose_result.blueprint_yaml)
            exec_result = self._engine.run(bp_def, inputs={"raw_api_response": raw_data})
            logger.debug("[BricksEngine] Execution outputs: %s", exec_result.outputs)
            return EngineResult(
                outputs=exec_result.outputs,
                tokens_in=compose_result.total_input_tokens,
                tokens_out=compose_result.total_output_tokens,
                duration_seconds=time.monotonic() - t0,
                model=compose_result.model,
                raw_response=compose_result.blueprint_yaml,
            )
        except Exception as exc:
            logger.error("[BricksEngine] Execution failed: %s", exc)
            return EngineResult(
                outputs={},
                tokens_in=compose_result.total_input_tokens,
                tokens_out=compose_result.total_output_tokens,
                duration_seconds=time.monotonic() - t0,
                model=compose_result.model,
                raw_response=compose_result.blueprint_yaml,
                error=str(exc),
            )

    def solve_reuse(self, blueprint_yaml: str, raw_data: str) -> EngineResult:
        """Execute an existing blueprint without recomposing (0 LLM tokens).

        Used by CRM-reuse scenario to demonstrate amortized compose cost.

        Args:
            blueprint_yaml: Previously composed blueprint YAML string.
            raw_data: Raw API response data.

        Returns:
            EngineResult with execution outputs and zero token counts.
        """
        t0 = time.monotonic()
        try:
            bp_def = self._loader.load_string(blueprint_yaml)
            exec_result = self._engine.run(bp_def, inputs={"raw_api_response": raw_data})
            return EngineResult(
                outputs=exec_result.outputs,
                tokens_in=0,
                tokens_out=0,
                duration_seconds=time.monotonic() - t0,
                model="cached",
                raw_response=blueprint_yaml,
            )
        except Exception as exc:
            logger.error("[BricksEngine.reuse] Execution failed: %s", exc)
            return EngineResult(
                outputs={},
                tokens_in=0,
                tokens_out=0,
                duration_seconds=time.monotonic() - t0,
                model="cached",
                raw_response=blueprint_yaml,
                error=str(exc),
            )


class RawLLMEngine(Engine):
    """Send task + data directly to LLM; parse JSON response as structured outputs.

    The LLM sees everything — task description AND the raw data — and is asked
    to reason and return a JSON object. No bricks, no blueprint, no execution.
    """

    _SYSTEM = (
        "You are a data analyst. Given a task description and raw data, "
        "compute the exact answer. Reply with ONLY a JSON object containing "
        "the requested output keys and their computed values. "
        "No code, no explanation, no markdown fences — just raw JSON."
    )

    def __init__(self, provider: Any) -> None:
        """Initialise with an LLMProvider.

        Args:
            provider: Any LLMProvider instance.
        """
        self._provider = provider

    def solve(self, task_text: str, raw_data: str) -> EngineResult:
        """Send task + raw_data to LLM, parse JSON response.

        Args:
            task_text: Natural language task description.
            raw_data: Raw data to include in the prompt.

        Returns:
            EngineResult with parsed JSON outputs. On JSON parse failure,
            outputs is an empty dict and error contains the parse exception.
        """
        prompt = (
            f"{task_text}\n\n"
            f"Here is the actual data:\n{raw_data}\n\n"
            "Compute the exact values. Return ONLY a JSON object."
        )

        t0 = time.monotonic()
        completion = self._provider.complete(prompt, system=self._SYSTEM)
        duration = time.monotonic() - t0

        raw_text = completion.text.strip()
        logger.debug("[RawLLMEngine] Raw response: %s", raw_text)

        outputs: dict[str, Any] = {}
        error = ""
        try:
            clean = raw_text
            if clean.startswith("```"):
                lines = clean.splitlines()
                end = -1 if lines[-1].strip() == "```" else len(lines)
                clean = "\n".join(lines[1:end])
            outputs = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as exc:
            error = f"JSON parse failed: {exc}"
            logger.warning("[RawLLMEngine] %s — raw: %.200s", error, raw_text)

        return EngineResult(
            outputs=outputs,
            tokens_in=completion.input_tokens,
            tokens_out=completion.output_tokens,
            duration_seconds=duration,
            model=completion.model,
            raw_response=raw_text,
            error=error,
        )
