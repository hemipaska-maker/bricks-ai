# Bricks

[![CI](https://github.com/hemipaska-maker/bricks/actions/workflows/ci.yml/badge.svg)](https://github.com/hemipaska-maker/bricks/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What is Bricks?

Bricks is a deterministic execution engine for AI agents. Instead of generating Python code at runtime, your AI composes reusable YAML blueprints from 100 pre-tested building blocks. Blueprints are validated before execution, produce identical results every run, and cost **zero tokens** after the first call.

**Benchmark:** 83% fewer tokens than code generation. 100% correctness vs ~60% for raw LLM output. Zero tokens on cached runs.

---

## Install

```bash
pip install bricks[stdlib,ai]
```

This installs the core engine + 100 stdlib bricks + LiteLLM for AI composition.

---

## Quick Start

```python
from bricks.api import Bricks

# One line setup — auto-discovers all installed brick packs
engine = Bricks.default()  # reads ANTHROPIC_API_KEY from environment

# Describe what you want in plain English
result = engine.execute(
    "filter active customers and count them",
    {"data": customers_list}
)

print(result["outputs"])      # {"active_customers": [...], "count": 42}
print(result["cache_hit"])    # True on second call — zero tokens!
print(result["tokens_used"])  # 0 on cache hit
```

The first call composes a blueprint (one LLM call). Every subsequent call with the same task reuses the saved blueprint at zero cost.

---

## MCP Setup

Use Bricks as an MCP server in Claude Desktop or any MCP-compatible host:

```json
{
  "mcpServers": {
    "bricks": {
      "command": "bricks",
      "args": ["serve"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Save this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Then Claude can call `execute_task` to run any task through Bricks.

---

## Why?

**Token savings.** Bricks composes once and reuses forever. Repeated tasks cost 0 tokens after the first call. In the CRM benchmark: 83% fewer tokens than raw code generation.

**Correctness.** Blueprints use typed, tested bricks — no hallucinated APIs, no variable name drift. 100% correctness vs ~60% for raw LLM output across 20 runs.

**Reuse.** Blueprints are plain YAML files. Save them, share them, version them. One blueprint handles 1000 different inputs.

**Auditability.** Every step is named. Every input/output is typed. You can inspect exactly what ran and why.

---

## Community Packs

Create a `bricks-{name}` package and publish it to PyPI. Users install it and it auto-registers:

```toml
# your-package/pyproject.toml
[project.entry-points."bricks.packs"]
mypack = "bricks_mypack"
```

```python
# bricks_mypack/__init__.py
from bricks.core.brick import brick
from bricks.core.registry import BrickRegistry

@brick(description="Fetch from my API")
def fetch_my_api(endpoint: str) -> dict:
    ...

def register(registry: BrickRegistry) -> None:
    registry.register("fetch_my_api", fetch_my_api, fetch_my_api.__brick_meta__)
```

After `pip install bricks-mypack`, `Bricks.default()` discovers and loads it automatically.

See `examples/agent.yaml` for a full configuration reference and `examples/skill.md` for how to describe a skill.
