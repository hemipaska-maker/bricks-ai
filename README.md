# Bricks

[![CI](https://github.com/hemipaska-maker/bricks-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/hemipaska-maker/bricks-ai/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**LLMs guess. Bricks computes.**

Bricks is a deterministic execution engine for AI agents. Your LLM writes a YAML blueprint from pre-tested building blocks. Bricks validates it, then executes it — same input, same output, every time. No hallucinated math. No format failures. No token burn on repeat runs.

---

## Prove It — 30 Seconds

```bash
git clone https://github.com/hemipaska-maker/bricks-ai.git
cd bricks
pip install -e ".[stdlib,ai]"
export ANTHROPIC_API_KEY=sk-ant-...       # or any supported LLM — see below
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline
```

Here's what you'll see — real results tested across three Claude models:

| | BricksEngine | Raw LLM |
|---|---|---|
| **Correctness** | **100%** (every model, every seed) | 0-60% (varies by model) |
| **Haiku** | ✅ `active_count: 18, revenue: 3447.50` | ❌ Hallucinated: `15, 3848.50` |
| **Sonnet** | ✅ Correct structured output | ❌ Wrote an essay instead of JSON |
| **10-run consistency** | **10/10 pass** | **6/10 pass** (4 hallucinated) |
| **20-run reuse** | **20/20 pass, 3,327 tokens total** | 12/20 pass, 75,880 tokens |

Bricks composed one blueprint, reused it 20 times at zero cost. The raw LLM called the API 20 times and still got 40% wrong.

---

## Bring Your Own LLM

Bricks works with any model. Blueprints are model-agnostic — compose with one LLM, execute anywhere.

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline

# OpenAI
export OPENAI_API_KEY=sk-...
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline --model gpt-4o-mini

# Google Gemini
export GOOGLE_API_KEY=AIza...
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline --model gemini/gemini-2.0-flash

# Local with Ollama (free, no API key)
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline --model ollama/llama3

# Claude Code Max plan ($0)
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline --model claudecode
```

---

## How It Works

```
Your task → LLM generates Python DSL → Bricks validates (AST) → Bricks executes deterministically
```

1. You describe what you want in plain English
2. The LLM picks from 100 pre-tested bricks and writes a Python DSL pipeline
   (validated with an AST whitelist before execution)
3. Bricks validates the blueprint (types, connections, missing inputs) before anything runs
4. Bricks executes it deterministically — same blueprint, any data, identical results
5. The blueprint is saved. Next time, zero LLM calls needed.

The LLM is used once, for planning. Execution is pure Python — no LLM in the loop, no token cost, no hallucination risk.

---

## Why Bricks?

**Correctness.** 100% across every model tested. Raw LLMs hallucinate numbers, ignore format instructions, and drift across runs. Bricks doesn't — every brick is typed and tested.

**Cost.** Compose once, reuse forever. 20 runs cost 3,327 tokens with Bricks vs 75,880 with raw LLM calls. That's a 95.6% reduction. After the first call, every repeat is free.

**Determinism.** Same blueprint + different data = guaranteed correct output. No randomness, no temperature, no "try again and hope."

**Auditability.** Blueprints are plain YAML. Every step is named, every input/output is typed. You can inspect, version, share, and review exactly what ran.

---

## Quick Start — Python API

```python
from bricks.api import Bricks

# One line setup — auto-discovers all installed brick packs
engine = Bricks.default()  # reads API key from environment

# Describe what you want in plain English
result = engine.execute(
    "filter active customers and count them",
    {"data": customers_list}
)

print(result["outputs"])      # {"active_customers": [...], "count": 42}
print(result["cache_hit"])    # True on second call — zero tokens!
print(result["tokens_used"])  # 0 on cache hit
```

---

## Python DSL

Write pipelines as Python instead of YAML. The `@flow` decorator traces the function once and builds a DAG:

```python
from bricks import step, for_each, branch, flow

# 1. Simple step chain
@flow
def clean_pipeline(data):
    cleaned = step.clean(text=data)
    return step.summarize(text=cleaned)

blueprint = clean_pipeline.to_blueprint()  # → BlueprintDefinition
yaml_str  = clean_pipeline.to_yaml()       # → YAML string

# 2. for_each — map a brick over every item in a list
@flow
def batch_clean(items):
    return for_each(items, do=lambda x: step.clean(text=x), on_error="collect")

# 3. branch — conditional routing
@flow
def route_record(record):
    return branch(
        condition="is_valid",
        if_true=lambda:  step.enrich(data=record),
        if_false=lambda: step.log_invalid(data=record),
    )
```

The LLM composer now generates Python DSL code instead of YAML.
Generated DSL is validated with an AST whitelist before execution.

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

Save this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

The MCP server exposes:
- **Tool:** `execute_task` — run any task through Bricks with optional `verbose` mode for step-by-step tracing
- **Resources:** `bricks://catalog` (all available bricks) and `bricks://blueprints` (cached blueprints)
- **Prompts:** templates for common tasks
- **Persistent store:** blueprints cache to `~/.bricks/blueprints` by default, surviving server restarts

---

## Install

```bash
# From source (recommended for now)
git clone https://github.com/hemipaska-maker/bricks-ai.git
cd bricks
pip install -e ".[stdlib,ai]"

# stdlib: 100 pre-tested bricks (data, string, math, validation, encoding)
# ai: LiteLLM for multi-provider LLM composition
```

---

## Windows Setup

On Windows, `pip install bricks-ai[ai]` can fail with a long-path error because `litellm` installs files whose paths exceed the Windows default 260-character limit (`MAX_PATH`).

**Symptom:**
```
ERROR: Could not install packages due to an OSError: [Errno 2] No such file or directory: '...\...\...'
```

**Fix (recommended):** Enable long paths via the registry or Group Policy:
1. Open `regedit`
2. Navigate to `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`
3. Set `LongPathsEnabled` to `1`
4. Restart your terminal

**Alternative:** Install in a short path (e.g. `C:\bricks\`) to stay under the 260-char limit.

**Verify your setup:**
```bash
bricks check-env
```

This command checks your Python version, litellm installation, and (on Windows) whether long paths are enabled.

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

---

## Benchmark: What's Actually Happening?

The CRM-pipeline benchmark generates 50 fake customer records and asks: "How many are active? What's their total revenue? What's the average?"

**The task prompt (what both engines receive):**

> Parse the JSON string, filter for status='active', count the active customers, sum their monthly_revenue, and compute the average revenue. Return: `active_count`, `total_active_revenue`, `avg_active_revenue`.

**The data (50 records, looks like this):**

```json
{
  "customers": [
    {"id": 1, "name": "Bob Jones", "email": "bob.jones0@example.com",
     "status": "active", "plan": "pro", "monthly_revenue": 109.0,
     "signup_date": "2020-07-07"},
    {"id": 2, "name": "Carol Smith", "email": "carol.smith1@example.com",
     "status": "inactive", "plan": "enterprise", "monthly_revenue": 514.5,
     "signup_date": "2021-02-02"},
    ...48 more records...
  ]
}
```

**What BricksEngine does:**

1. LLM reads the task and the brick catalog (not the data) → composes a YAML blueprint:
   `extract_json_from_str → filter_dict_list(status=active) → count_dict_list → calculate_aggregates(sum, avg)`
2. Bricks validates the blueprint (types, connections, missing inputs)
3. Bricks executes it deterministically with the 50 records
4. Returns: `{"active_count": 18, "total_active_revenue": 3447.50, "avg_active_revenue": 191.53}` ✅

**What RawLLMEngine does:**

1. LLM receives the task AND the full 50-record JSON
2. LLM tries to count, sum, and average in its head
3. Returns... it depends on the model:
   - **Haiku**: `{"active_count": 15, "total_active_revenue": 3848.50, ...}` ❌ (hallucinated numbers)
   - **Sonnet**: `"Let me analyze this step by step. First, I'll identify..."` ❌ (essay instead of JSON)
   - **ClaudeCode**: sometimes correct, sometimes wrong — 60% pass rate over 10 runs

**The key insight:** Bricks uses the LLM only for planning (which bricks to chain). The actual math runs in deterministic Python. The raw LLM has to do everything — read 50 records, count, sum, divide — in one shot. That's where hallucination happens.

---

## Try It Instantly — Interactive Demo

No API key needed. See Bricks in action right in your terminal:

```bash
bricks demo
```

Three acts: compose a blueprint, execute it on CRM data, compare Bricks vs raw LLM. Run `bricks demo --act 1` for just the first act.

---

## Benchmark Scenarios

Run the full benchmark suite:

```bash
python -m bricks_benchmark.showcase.run --live                         # all scenarios
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline # single scenario
python -m bricks_benchmark.showcase.run --live --scenario TICKET-pipeline  # support tickets
```

| Scenario | What it proves | Bricks | Raw LLM |
|----------|---------------|--------|---------|
| **CRM-pipeline** | Determinism beats reasoning | ✅ Correct | ❌ Wrong (hallucination or format failure) |
| **CRM-hallucination** | Consistency at scale (10 runs) | 10/10 (100%) | 6/10 (60%) |
| **CRM-reuse** | Zero cost after first run (20 runs) | 20/20, 3,327 tokens | 12/20, 75,880 tokens |
| **TICKET-pipeline** | Generalizes to new domains | ✅ Correct | ❌ Struggles with PII + filtering |

Tested with ClaudeCode, Claude Haiku, and Claude Sonnet.
