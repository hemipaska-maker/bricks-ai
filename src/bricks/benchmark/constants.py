"""Shared constants for the benchmark suite."""

from __future__ import annotations

from enum import Enum

DEFAULT_MODEL: str = "claude-haiku-4-5-20251001"
MAX_TOKENS: int = 2048
FLOAT_TOLERANCE: float = 0.01
CHARS_PER_TOKEN: int = 4
PRICE_INPUT_PER_M: float = 0.80
PRICE_OUTPUT_PER_M: float = 4.00

MAX_TURNS: int = 20
REUSE_RUNS: int = 10
DETERMINISM_RUNS: int = 5


class RunMode(str, Enum):
    """Benchmark execution modes."""

    TOOL_USE = "tool_use"
    COMPOSE = "compose"


class RunStatus(str, Enum):
    """Benchmark result status labels."""

    OK = "OK correct"
    WRONG = "WRONG silent"
    CAUGHT = "CAUGHT pre-exec"
    CLEAR = "CLEAR error"
    CRASH = "CRASH runtime"
