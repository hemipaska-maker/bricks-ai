"""Token estimation for Bricks vs Python approaches."""

from __future__ import annotations

from dataclasses import dataclass

from bricks.playground.scenarios import Scenario

# Approximate Bricks system prompt size (~180 words)
_BRICKS_SYSTEM_PROMPT_CHARS = 960
# Approximate Python system prompt size (must describe functions verbosely)
_PYTHON_SYSTEM_PROMPT_CHARS = 1600
# Average chars per brick schema in JSON
_CHARS_PER_BRICK_SCHEMA = 200
# Average chars for Python function docstring + signature
_CHARS_PER_PYTHON_FUNC = 400
# Number of domain bricks
_NUM_BRICKS = 10
# Error correction: re-prompt with error trace + original code
_PYTHON_ERROR_CORRECTION_CHARS = 2000


def _chars_to_tokens(chars: int) -> int:
    """Estimate tokens from character count (~4 chars per token)."""
    return max(1, chars // 4)


@dataclass
class TokenEstimate:
    """Estimated token usage for one scenario under one approach."""

    system_prompt: int
    generation_input: int
    generation_output: int
    error_correction: int
    reuse_cost: int

    @property
    def total(self) -> int:
        """Sum of all token components."""
        return (
            self.system_prompt
            + self.generation_input
            + self.generation_output
            + self.error_correction
            + self.reuse_cost
        )


class TokenEstimator:
    """Estimates token usage for Bricks and Python approaches."""

    def estimate_bricks(
        self,
        scenario: Scenario,
        had_error: bool = False,
    ) -> TokenEstimate:
        """Return token usage for the Bricks (YAML) approach.

        In live mode uses real API token counts. Raises if live tokens are
        missing. In demo mode falls back to character-count estimates.
        """
        if scenario.live_mode:
            if not scenario.live_bricks_tokens:
                raise RuntimeError(f"Live mode enabled but live_bricks_tokens not set for scenario '{scenario.name}'")
            return TokenEstimate(
                system_prompt=0,
                generation_input=scenario.live_bricks_tokens,
                generation_output=0,
                error_correction=0,
                reuse_cost=0,
            )
        system_prompt = _chars_to_tokens(_BRICKS_SYSTEM_PROMPT_CHARS)
        brick_context = _chars_to_tokens(_CHARS_PER_BRICK_SCHEMA * _NUM_BRICKS)
        intent_tokens = _chars_to_tokens(len(scenario.intent))
        generation_input = brick_context + intent_tokens
        generation_output = _chars_to_tokens(len(scenario.bricks_yaml))
        return TokenEstimate(
            system_prompt=system_prompt,
            generation_input=generation_input,
            generation_output=generation_output,
            error_correction=0,
            reuse_cost=0,
        )

    def estimate_python(
        self,
        scenario: Scenario,
        had_error: bool = False,
    ) -> TokenEstimate:
        """Return token usage for the raw Python approach.

        In live mode uses real API token counts. Raises if live tokens are
        missing. In demo mode falls back to character-count estimates.

        Args:
            scenario: The benchmark scenario.
            had_error: Whether the Python code caused a runtime error
                       (requires a full re-prompt to fix).
        """
        if scenario.live_mode:
            if not scenario.live_python_tokens:
                raise RuntimeError(f"Live mode enabled but live_python_tokens not set for scenario '{scenario.name}'")
            error_correction = _chars_to_tokens(_PYTHON_ERROR_CORRECTION_CHARS) if had_error else 0
            reuse_cost = 0
            if scenario.extra_inputs:
                reuse_cost = scenario.live_python_tokens * len(scenario.extra_inputs)
            return TokenEstimate(
                system_prompt=0,
                generation_input=scenario.live_python_tokens,
                generation_output=0,
                error_correction=error_correction,
                reuse_cost=reuse_cost,
            )
        system_prompt = _chars_to_tokens(_PYTHON_SYSTEM_PROMPT_CHARS)
        func_context = _chars_to_tokens(_CHARS_PER_PYTHON_FUNC * _NUM_BRICKS)
        intent_tokens = _chars_to_tokens(len(scenario.intent))
        generation_input = func_context + intent_tokens
        generation_output = _chars_to_tokens(len(scenario.python_code))
        error_correction = _chars_to_tokens(_PYTHON_ERROR_CORRECTION_CHARS) if had_error else 0
        reuse_cost = 0
        if scenario.extra_inputs:
            per_run = generation_input + generation_output
            reuse_cost = per_run * len(scenario.extra_inputs)
        return TokenEstimate(
            system_prompt=system_prompt,
            generation_input=generation_input,
            generation_output=generation_output,
            error_correction=error_correction,
            reuse_cost=reuse_cost,
        )

    def estimate_pair(
        self,
        scenario: Scenario,
        bricks_had_error: bool = False,
        python_had_error: bool = False,
    ) -> tuple[TokenEstimate, TokenEstimate]:
        """Return (bricks_estimate, python_estimate) for a scenario."""
        return (
            self.estimate_bricks(scenario, bricks_had_error),
            self.estimate_python(scenario, python_had_error),
        )
