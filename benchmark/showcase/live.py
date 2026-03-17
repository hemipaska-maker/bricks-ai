"""Live mode: real Anthropic API calls with logging for the showcase benchmark."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from bricks.core import BrickRegistry
from bricks.core.utils import blueprint_to_yaml, strip_code_fence


def setup_logger(output_dir: Path) -> tuple[logging.Logger, Path]:
    """Create a logger that writes to console (INFO) and a log file (DEBUG).

    Args:
        output_dir: Directory where ``benchmark_live.log`` will be written.

    Returns:
        (logger, log_file_path)
    """
    log_path = output_dir / "benchmark_live.log"

    logger = logging.getLogger("bricks.showcase")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler: full DEBUG detail
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # Console handler: INFO summary only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("    %(message)s"))
    logger.addHandler(ch)

    return logger, log_path


def bricks_api_call(
    intent: str,
    registry: BrickRegistry,
    logger: logging.Logger,
    label: str = "bricks",
) -> tuple[str, int, int]:
    """Call BlueprintComposer and return (yaml_str, input_tokens, output_tokens).

    Args:
        intent: Natural language task description.
        registry: Brick registry with available bricks.
        logger: Logger for recording call details.
        label: Short identifier used in log messages.

    Returns:
        (yaml_str, input_tokens, output_tokens) as reported by the API.
    """
    from bricks.ai import BlueprintComposer

    api_key = _require_api_key()
    composer = BlueprintComposer(registry=registry, api_key=api_key)

    logger.info("[%s] API call -> YAML generation", label)
    logger.debug("[%s] intent: %s", label, intent)

    t0 = time.monotonic()
    sequence, in_tok, out_tok = composer.compose_with_usage(intent)
    elapsed = time.monotonic() - t0

    logger.info(
        "[%s] done  input=%d  output=%d  total=%d tokens  (%.2fs)",
        label,
        in_tok,
        out_tok,
        in_tok + out_tok,
        elapsed,
    )

    yaml_str = blueprint_to_yaml(sequence)
    logger.debug("[%s] generated YAML:\n%s", label, yaml_str)

    return yaml_str, in_tok, out_tok


def python_api_call(
    system_prompt: str,
    user_prompt: str,
    logger: logging.Logger,
    label: str = "python",
) -> tuple[str, int, int]:
    """Generate Python code via Anthropic API.

    Args:
        system_prompt: System prompt (function signatures + rules).
        user_prompt: User prompt (task description).
        logger: Logger for recording call details.
        label: Short identifier used in log messages.

    Returns:
        (code, input_tokens, output_tokens) as reported by the API.
    """
    import anthropic  # type: ignore[import-not-found]

    api_key = _require_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    logger.info("[%s] API call -> Python generation", label)
    logger.debug("[%s] user_prompt:\n%s", label, user_prompt)

    t0 = time.monotonic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    elapsed = time.monotonic() - t0

    in_tok: int = response.usage.input_tokens
    out_tok: int = response.usage.output_tokens
    code = strip_code_fence(response.content[0].text)

    logger.info(
        "[%s] done  input=%d  output=%d  total=%d tokens  (%.2fs)",
        label,
        in_tok,
        out_tok,
        in_tok + out_tok,
        elapsed,
    )
    logger.debug("[%s] generated code:\n%s", label, code)

    return code, in_tok, out_tok


# ── private helpers ─────────────────────────────────────────────────────────


def _require_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is not set.\nExport it before running:  export ANTHROPIC_API_KEY=sk-...")
    return key
