# bricks-ai

**LLMs guess. Bricks computes.**

Bricks is a deterministic execution engine for AI agents. Your LLM writes a YAML blueprint from pre-tested building blocks. Bricks validates it, then executes it — same input, same output, every time.

## Install

```bash
pip install bricks-ai
pip install "bricks-ai[stdlib,ai]"   # with standard library and LLM support
```

## Quick Start

```python
from bricks.api import Bricks

engine = Bricks.default()
result = engine.execute(
    "filter active customers and count them",
    {"data": customers_list}
)
print(result["outputs"])   # {"active_customers": [...], "count": 42}
print(result["cache_hit"]) # True on second call — zero tokens!
```

## Interactive Demo

No API key needed:

```bash
bricks demo           # full 3-act demo
bricks demo --act 1   # just blueprint composition
```

## MCP Server

Expose Bricks as a tool for Claude Desktop or any MCP client:

```bash
bricks serve
```

Features: `execute_task` tool with verbose mode, `bricks://catalog` and `bricks://blueprints` resources, prompt templates, persistent file-based blueprint cache.

## CLI

```bash
bricks --help          # see all commands
bricks demo            # interactive demo
bricks serve           # start MCP server
bricks check-env       # verify your setup (Python, deps, Windows long paths)
```

## Full Documentation

See the [main repository README](https://github.com/hemipaska-maker/bricks-ai#readme) for full documentation, benchmarks, and examples.
