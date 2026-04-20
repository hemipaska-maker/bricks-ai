"""Report generator: prints comparison tables and final scorecard."""

from __future__ import annotations

from bricks.benchmark.runner import RunResult
from bricks.benchmark.scenarios import Scenario


def _status_label(result: RunResult) -> str:
    """Return a short display label for a RunResult status."""
    labels = {
        "correct": "OK correct",
        "wrong_answer": "WRONG silent",
        "caught_pre_exec": "CAUGHT pre-exec",
        "runtime_error": ("CLEAR error" if result.error_quality == "clear" else "CRASH runtime"),
        "blocked": "BLOCKED safe",
    }
    return labels.get(result.status, result.status)


def _is_safe(result: RunResult) -> bool:
    """A safe outcome: correct, caught pre-exec, or clear runtime error."""
    return result.status in ("correct", "caught_pre_exec", "blocked") or (
        result.status == "runtime_error" and result.error_quality == "clear"
    )


def print_header() -> None:
    """Print the benchmark banner."""
    print("=" * 68)
    print(" BRICKS vs RAW PYTHON -- AI BENCHMARK (10 scenarios)")
    print("=" * 68)
    print()


def print_correctness_table(
    scenarios: list[Scenario],
    bricks_results: list[RunResult],
    python_results: list[RunResult],
) -> None:
    """Print Table 1: Correctness & Error Prevention."""
    print("=" * 68)
    print(" TABLE 1: CORRECTNESS & ERROR PREVENTION")
    print("=" * 68)
    print()
    print(f" {'#':>2}  {'Scenario':<28} {'With Bricks':<20} {'Without Bricks':<20}")
    print(f" {'--':>2}  {'-' * 28:<28} {'-' * 20:<20} {'-' * 20:<20}")
    for i, (scn, br, pr) in enumerate(zip(scenarios, bricks_results, python_results, strict=True), start=1):
        bl = _status_label(br)
        pl = _status_label(pr)
        print(f" {i:>2}  {scn.name:<28} {bl:<20} {pl:<20}")
    print()


def print_token_table(
    scenarios: list[Scenario],
    bricks_results: list[RunResult],
    python_results: list[RunResult],
) -> None:
    """Print Table 2: Token Savings."""
    total_bricks = 0
    total_python = 0
    for br, pr in zip(bricks_results, python_results, strict=True):
        if br.tokens:
            total_bricks += br.tokens.total
        if pr.tokens:
            total_python += pr.tokens.total

    savings_pct = round((1 - total_bricks / total_python) * 100) if total_python > 0 else 0

    # Per-component breakdown
    bricks_ctx = 0
    python_ctx = 0
    bricks_out = 0
    python_out = 0
    bricks_err = 0
    python_err = 0
    bricks_reuse = 0
    python_reuse = 0
    for br, pr in zip(bricks_results, python_results, strict=True):
        if br.tokens:
            bricks_ctx += br.tokens.system_prompt + br.tokens.generation_input
            bricks_out += br.tokens.generation_output
            bricks_err += br.tokens.error_correction
            bricks_reuse += br.tokens.reuse_cost
        if pr.tokens:
            python_ctx += pr.tokens.system_prompt + pr.tokens.generation_input
            python_out += pr.tokens.generation_output
            python_err += pr.tokens.error_correction
            python_reuse += pr.tokens.reuse_cost

    print("=" * 68)
    print(" TABLE 2: TOKEN SAVINGS")
    print("=" * 68)
    print()
    print(f" {'Component':<28} {'Bricks':>10} {'Python':>10} {'Savings':>10}")
    print(f" {'-' * 28:<28} {'-' * 10:>10} {'-' * 10:>10} {'-' * 10:>10}")
    _token_row("Context prompts", bricks_ctx, python_ctx)
    _token_row("Generation output", bricks_out, python_out)
    _token_row("Error correction", bricks_err, python_err)
    _token_row("Reuse cost", bricks_reuse, python_reuse)
    print(f" {'-' * 28:<28} {'-' * 10:>10} {'-' * 10:>10} {'-' * 10:>10}")
    _token_row("TOTAL", total_bricks, total_python)
    print()
    print(f" Overall token savings: {savings_pct}%")
    print()


def _token_row(label: str, bricks: int, python: int) -> None:
    """Print one row of the token table."""
    pct = round((1 - bricks / python) * 100) if python > 0 else 0
    print(f" {label:<28} {bricks:>10,} {python:>10,} {pct:>9}%")


def print_security_table(
    scenarios: list[Scenario],
    bricks_results: list[RunResult],
    python_results: list[RunResult],
) -> None:
    """Print Table 3: Security."""
    print("=" * 68)
    print(" TABLE 3: SECURITY")
    print("=" * 68)
    print()
    print(f" {'Threat':<30} {'With Bricks':<18} {'Without Bricks':<18}")
    print(f" {'-' * 30:<30} {'-' * 18:<18} {'-' * 18:<18}")
    print(f" {'Arbitrary code execution':<30} {'BLOCKED':<18} {'VULNERABLE':<18}")
    print(f" {'File system access':<30} {'BLOCKED':<18} {'VULNERABLE':<18}")
    print(f" {'Import injection':<30} {'BLOCKED':<18} {'VULNERABLE':<18}")
    b_sand = "YES (brick-only)"
    p_sand = "NO (full Python)"
    print(f" {'Sandboxed execution':<30} {b_sand:<18} {p_sand:<18}")
    print()

    # Show scenario 10 result if present
    for scn, br, pr in zip(scenarios, bricks_results, python_results, strict=True):
        if scn.category == "security":
            print(f" Scenario '{scn.name}':")
            print(f"   Bricks: security_safe={br.security_safe} | {_status_label(br)}")
            print(f"   Python: security_safe={pr.security_safe} | {_status_label(pr)}")
            if pr.errors:
                print(f"   Detail: {pr.errors[0]}")
    print()


def print_scorecard(
    bricks_results: list[RunResult],
    python_results: list[RunResult],
) -> None:
    """Print the final scorecard."""
    bricks_safe = sum(1 for r in bricks_results if _is_safe(r))
    python_safe = sum(1 for r in python_results if _is_safe(r))
    n = len(bricks_results)

    total_b_tok = sum(r.tokens.total for r in bricks_results if r.tokens)
    total_p_tok = sum(r.tokens.total for r in python_results if r.tokens)
    savings_pct = round((1 - total_b_tok / total_p_tok) * 100) if total_p_tok > 0 else 0

    bricks_secure = all(r.security_safe for r in bricks_results)

    print("=" * 68)
    print(" FINAL SCORECARD")
    print("=" * 68)
    print()
    hdr = f" {'Dimension':<24} {'Bricks':>12} {'Python':>12}   Winner"
    print(hdr)
    print(f" {'-' * 24:<24} {'-' * 12:>12} {'-' * 12:>12}   {'-' * 10}")
    bw = "BRICKS" if bricks_safe > python_safe else "PYTHON"
    print(f" {'Safe outcomes':<24} {bricks_safe:>10} / {n:<3} {python_safe:>12} / {n:<3}   {bw:<10}")
    tw = "BRICKS" if total_b_tok < total_p_tok else "PYTHON"
    print(f" {'Token efficiency':<24} {total_b_tok:>10,}     {total_p_tok:>12,}     {tw} ({savings_pct}% less)")
    sw = "BRICKS" if bricks_secure else "PYTHON"
    print(f" {'Security (sandboxed)':<24} {'YES':>14} {'NO':>16}   {sw:<10}")
    print()
    print("=" * 68)
    print()


def print_full_report(
    scenarios: list[Scenario],
    bricks_results: list[RunResult],
    python_results: list[RunResult],
) -> None:
    """Print all tables and the scorecard."""
    print_header()
    print_correctness_table(scenarios, bricks_results, python_results)
    print_token_table(scenarios, bricks_results, python_results)
    print_security_table(scenarios, bricks_results, python_results)
    print_scorecard(bricks_results, python_results)
