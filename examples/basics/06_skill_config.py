"""06 — Skill Config: boot Bricks from a config file or skill description.

Demonstrates two config-driven boot patterns:

  from_config(path)  — reads ``agent.yaml``, no LLM call, no API key needed.
  from_skill(path)   — reads ``skill.md``, makes one LLM call to extract domain
                       keywords, then all execute() calls are deterministic.

Run::

    python examples/basics/06_skill_config.py

For the live (from_skill) section, set your API key::

    ANTHROPIC_API_KEY=sk-ant-... python examples/basics/06_skill_config.py
"""

from __future__ import annotations

import os
from pathlib import Path

from bricks import Bricks

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_AGENT_YAML = _CONFIG_DIR / "agent.yaml"
_SKILL_MD = _CONFIG_DIR / "skill.md"


def demo_from_config() -> None:
    """Boot from agent.yaml — zero LLM calls, no API key needed."""
    print("--- from_config() ---")
    engine = Bricks.from_config(_AGENT_YAML)
    print(f"  Booted from {_AGENT_YAML.name}")
    print("  Engine ready. Call engine.execute(task, inputs) to run a task.")
    print("  (Actual execution requires an API key for blueprint composition.)")
    _ = engine  # engine is ready; not executing to avoid requiring an API key


def demo_from_skill() -> None:
    """Boot from skill.md — one LLM call on boot, then zero per task."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("--- from_skill() ---")
        print("  Skipped: set ANTHROPIC_API_KEY to run the live from_skill demo.")
        return

    print("--- from_skill() (live) ---")
    engine = Bricks.from_skill(_SKILL_MD, api_key=api_key)
    print(f"  Booted from {_SKILL_MD.name} (one LLM call to extract domain)")
    print("  Engine ready for CRM tasks — subsequent calls use cached blueprint.")
    _ = engine


if __name__ == "__main__":
    demo_from_config()
    print()
    demo_from_skill()
    print()
    print("OK")
