"""Run metadata: git info, SDK version, and metadata file writing."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bricks import __version__
from bricks.playground.constants import DEFAULT_MODEL


def git_info() -> tuple[str, str, bool]:
    """Return (commit_hash, branch, is_dirty).

    Returns:
        Tuple of (short commit hash, branch name, dirty flag).
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return commit, branch, dirty
    except Exception:
        return "unknown", "unknown", False


def anthropic_sdk_version() -> str:
    """Return installed anthropic SDK version or 'not installed'.

    Returns:
        Version string or 'not installed'.
    """
    try:
        import anthropic  # type: ignore[import-not-found]

        return str(anthropic.__version__)
    except Exception:
        return "not installed"


def make_run_dir(output_dir: Path) -> Path:
    """Create and return a unique timestamped run directory.

    Args:
        output_dir: Base output directory.

    Returns:
        Path to the new run directory.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{ts}_v{__version__}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_metadata(
    run_dir: Path,
    scenarios_run: list[str],
    model: str = DEFAULT_MODEL,
) -> Path:
    """Write run_metadata.json to run_dir and return the path.

    Args:
        run_dir: Directory to write metadata into.
        scenarios_run: List of scenario labels that were run.
        model: LiteLLM model string used for the benchmark run.

    Returns:
        Path to the written metadata file.
    """
    commit, branch, dirty = git_info()
    metadata: dict[str, object] = {
        "bricks_version": __version__,
        "python_version": sys.version.split()[0],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ai_model": model,
        "ai_provider": "anthropic",
        "anthropic_sdk_version": anthropic_sdk_version(),
        "mode": "live",
        "command": " ".join(["python", "-m", "benchmark.showcase.run", *sys.argv[1:]]),
        "scenarios_run": scenarios_run,
        "os": f"{platform.system()} {platform.release()}",
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": dirty,
    }
    out = run_dir / "run_metadata.json"
    out.write_text(json.dumps(metadata, indent=2))
    return out
