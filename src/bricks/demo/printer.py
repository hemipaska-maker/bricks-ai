"""Rich-based terminal output helpers for the Bricks demo."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from bricks.demo.data import (
    DEMO_COMPOSE_TOKENS,
    DEMO_LLM_PER_RUN_TOKENS,
    DemoMetrics,
)

_console = Console()

_DIVIDER = "-" * 50


def act_header(n: int, title: str) -> None:
    """Print a bold act header.

    Args:
        n: Act number (1, 2, or 3).
        title: Act title.
    """
    _console.print()
    _console.print(f"[bold cyan]=== Act {n}: {title} ===[/bold cyan]")
    _console.print()


def divider() -> None:
    """Print a subtle horizontal divider."""
    _console.print(f"[dim]{_DIVIDER}[/dim]")
    _console.print()


def print_message(message: str) -> None:
    """Print a plain informational message.

    Args:
        message: Text to display.
    """
    _console.print(message)


def print_mode(mode: str) -> None:
    """Print the current running mode (LIVE or DEMO).

    Args:
        mode: Mode label string.
    """
    if "LIVE" in mode:
        _console.print(f"[bold green]  {mode}[/bold green]")
    else:
        _console.print(f"[dim]  {mode}[/dim]")
    _console.print()


def show_customer_table(records: list[dict[str, Any]], title: str = "CRM Data") -> None:
    """Display a list of customer dicts as a rich table.

    Args:
        records: List of customer dicts.
        title: Table title.
    """
    if not records:
        return
    table = Table(title=title, show_header=True, header_style="bold blue")
    columns = list(records[0].keys())
    for col in columns:
        table.add_column(col.replace("_", " ").title())
    for row in records:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    _console.print(table)
    _console.print()


def show_yaml(yaml_str: str, title: str = "Blueprint YAML") -> None:
    """Display syntax-highlighted YAML.

    Args:
        yaml_str: YAML string to display.
        title: Title shown above the code block.
    """
    _console.print(f"[bold]{title}[/bold]")
    syntax = Syntax(yaml_str.strip(), "yaml", theme="monokai", line_numbers=False)
    _console.print(syntax)
    _console.print()


def show_result(key: str, value: float) -> None:
    """Display an execution result in green.

    Args:
        key: Output key name.
        value: Numeric value.
    """
    _console.print(f"[bold green]  Result: {key} = {value}[/bold green]")
    _console.print()


def show_run_result(
    n: int,
    bricks_correct: bool,
    bricks_value: float,
    llm_value: float | None,
    expected: float,
) -> None:
    """Display a single Act 2 run result row.

    Args:
        n: Run number (1-5).
        bricks_correct: Whether the Bricks result matched expected.
        bricks_value: Value returned by Bricks.
        llm_value: Value returned by raw LLM (None if unparseable).
        expected: Ground-truth expected value.
    """
    b_mark = "[bold green]OK[/bold green]" if bricks_correct else "[bold red]FAIL[/bold red]"
    if llm_value is None:
        l_mark = "[bold red]FAIL (parse error)[/bold red]"
    elif abs(llm_value - expected) < 0.01:
        l_mark = "[bold green]OK[/bold green]"
    else:
        l_mark = f"[bold red]FAIL ({llm_value} != {expected})[/bold red]"

    _console.print(f"  Run {n}:  Bricks {b_mark}  ({bricks_value})  |  Raw LLM {l_mark}")


def show_token_table(metrics: DemoMetrics) -> None:
    """Display the Act 3 token comparison table.

    Args:
        metrics: Accumulated metrics from Acts 1 and 2.
    """
    label = "actual" if metrics.live else "estimated"
    n = metrics.num_variants

    compose_b = metrics.compose_tokens if metrics.live else DEMO_COMPOSE_TOKENS
    per_run_llm = (metrics.llm_run_tokens // n) if (metrics.live and n > 0) else DEMO_LLM_PER_RUN_TOKENS

    total_b = compose_b + metrics.bricks_run_tokens
    total_l = per_run_llm * n

    table = Table(
        title=f"Token Comparison ({label})",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Step", style="bold")
    table.add_column("Bricks", justify="right", style="green")
    table.add_column("Raw LLM", justify="right", style="yellow")

    table.add_row("Compose:", f"~{compose_b:,}", "n/a")
    for i in range(1, n + 1):
        cached_label = "0 (cached)" if i > 1 or not metrics.live else "0"
        table.add_row(f"Run {i}:", cached_label, f"~{per_run_llm:,}")

    table.add_section()
    table.add_row(
        f"Total ({n} runs):",
        f"[bold green]~{total_b:,}[/bold green]",
        f"[bold yellow]~{total_l:,}[/bold yellow]",
    )
    if total_l > 0:
        savings_pct = int((total_l - total_b) / total_l * 100)
        table.add_row(
            "Savings:",
            f"[bold green]{savings_pct}%[/bold green]",
            "",
        )

    _console.print(table)
    _console.print()

    # Scale projection
    scale_runs = 20
    scale_b = compose_b
    scale_l = per_run_llm * scale_runs
    scale_savings = int((scale_l - scale_b) / scale_l * 100) if scale_l > 0 else 0
    _console.print(
        f"[dim]At {scale_runs} runs: Bricks ~{scale_b:,} tokens, "
        f"Raw LLM ~{scale_l:,} tokens ({scale_savings}% savings)[/dim]"
    )
    _console.print()


def print_summary_line(bricks_score: int, llm_score: int, total: int) -> None:
    """Print the Act 2 summary comparison line.

    Args:
        bricks_score: Number of correct Bricks results.
        llm_score: Number of correct raw LLM results.
        total: Total number of runs.
    """
    b_color = "green" if bricks_score == total else "yellow"
    l_color = "green" if llm_score == total else "red"
    _console.print()
    _console.print(
        f"  [bold {b_color}]Bricks: {bricks_score}/{total} correct.[/bold {b_color}]  "
        f"[bold {l_color}]Raw LLM: {llm_score}/{total}.[/bold {l_color}]  "
        "[dim]Deterministic beats probabilistic.[/dim]"
    )
    _console.print()


def print_welcome() -> None:
    """Print the opening welcome banner."""
    welcome = Text()
    welcome.append("Bricks", style="bold cyan")
    welcome.append(" -- let's build a pipeline in 30 seconds", style="bold")
    _console.print()
    _console.print(welcome)


def print_closing() -> None:
    """Print the demo closing hints."""
    _console.print("[bold]Try it yourself:[/bold]")
    _console.print("  [cyan]bricks demo --act 1[/cyan]")
    _console.print("  [cyan]bricks demo --provider claudecode[/cyan]")
    _console.print()
    _console.print("[dim]Full benchmark: python -m bricks.benchmark.showcase.run --live[/dim]")
    _console.print()


@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    """Display a spinner while a block of work runs.

    Args:
        message: Text shown next to the spinner.

    Yields:
        None — the caller's body runs inside the spinner context.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=_console,
    ) as progress:
        progress.add_task(description=message, total=None)
        yield
