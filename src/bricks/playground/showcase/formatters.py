"""Table printing, cost formatting, and summary output for benchmark results."""

from __future__ import annotations

from typing import Any

from bricks.playground.constants import DEFAULT_MODEL, PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for the given token counts.

    Args:
        input_tokens: Total input tokens.
        output_tokens: Total output tokens.

    Returns:
        Estimated cost in USD.
    """
    return (input_tokens * PRICE_INPUT_PER_M + output_tokens * PRICE_OUTPUT_PER_M) / 1_000_000


def print_a2_table(a2_results: list[dict[str, Any]]) -> None:
    """Print the A complexity curve summary table.

    Args:
        a2_results: List of comparison dicts from A-N scenarios.
    """
    print()
    print("  +----------+------------+------------+--------+--------------+")
    print("  | Task     | No Tools   | Bricks     | Ratio  | Bricks turns |")
    print("  +----------+------------+------------+--------+--------------+")
    for r in a2_results:
        nt = r["no_tools"]["total_tokens"]
        br = r["bricks"]["total_tokens"]
        ratio = f"{nt / br:.1f}x" if br > 0 else "inf"
        turns = r["bricks"]["turns"]
        print(f"  | {r['label']:<8} | {nt:>10,} | {br:>10,} | {ratio:>6} | {turns:>12} |")
    print("  +----------+------------+------------+--------+--------------+")
    print()


def print_cost_summary(
    total_input: int,
    total_output: int,
    elapsed: float,
) -> None:
    """Print the total cost summary footer.

    Args:
        total_input: Total input tokens across all scenarios.
        total_output: Total output tokens across all scenarios.
        elapsed: Total elapsed time in seconds.
    """
    total = total_input + total_output
    cost = estimate_cost(total_input, total_output)
    print(f"  Total: {total:,} tokens used (input: {total_input:,} + output: {total_output:,})")
    print(f"  Estimated cost: ~${cost:.3f} ({DEFAULT_MODEL})")
    print(f"  Elapsed: {elapsed:.1f}s")
    print()


def count_yaml_steps(yaml_text: str) -> int:
    """Count steps in a YAML blueprint string.

    Args:
        yaml_text: Raw YAML string.

    Returns:
        Number of ``- name:`` entries found.
    """
    return yaml_text.count("- name:")


def log_compose_calls(
    label: str,
    result: Any,
    logger: Any,
) -> None:
    """Print and log per-call detail for a compose result.

    Args:
        label: Scenario label (e.g. 'A-12').
        result: ComposeResult with calls list.
        logger: Logger for DEBUG-level detail.
    """
    for call in result.calls:
        suffix = " (retry)" if call.call_number > 1 else ""
        total = call.input_tokens + call.output_tokens
        print(
            f"  [{label}] Call {call.call_number}/compose{suffix}: "
            f"{call.input_tokens:,} input + {call.output_tokens:,} output "
            f"= {total:,} tokens ({call.duration_seconds:.1f}s)"
        )

        lines = len(call.yaml_text.strip().splitlines())
        steps = count_yaml_steps(call.yaml_text)
        print(f"  [{label}]   YAML: {lines} lines, {steps} steps")

        if call.is_valid:
            print(f"  [{label}]   Validation: OK")
        else:
            errors_str = "; ".join(call.validation_errors[:3])
            print(f"  [{label}]   Validation: FAILED — {errors_str}")

        logger.debug("%s call %d YAML:\n%s", label, call.call_number, call.yaml_text)
        if call.validation_errors:
            logger.debug(
                "%s call %d errors: %s",
                label,
                call.call_number,
                call.validation_errors,
            )
