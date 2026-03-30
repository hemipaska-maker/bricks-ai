# Bricks CRM Benchmark

> Controlled comparison: Bricks compose vs raw LLM on real-world CRM data processing tasks.

## How It Works

Both engines receive **identical input** (task description + raw API data) and are evaluated with the same `check_correctness()` function. Only the system under test changes.

```
BricksEngine:   task_text → BlueprintComposer → YAML → BlueprintEngine(raw_data) → outputs
RawLLMEngine:   task_text + raw_data → LLM(JSON prompt) → parse JSON → outputs
```

## Scenarios

| Scenario | Description |
|---|---|
| **CRM-pipeline** | 1 compose run on seed=42; check active_count, total_active_revenue, avg_active_revenue |
| **CRM-hallucination** | 10x runs (different seeds); compare pass rates across both engines |
| **CRM-reuse** | Compose blueprint once (seed=42), reuse for 19 more seeds; measure token amortization |

## Run It

```bash
# From the project root (inside a Claude Code session for zero-cost runs)
python -m bricks_benchmark.showcase.run --live --claudecode

# Specific scenario
python -m bricks_benchmark.showcase.run --live --claudecode --scenario CRM-pipeline
python -m bricks_benchmark.showcase.run --live --claudecode --scenario CRM-hallucination
python -m bricks_benchmark.showcase.run --live --claudecode --scenario CRM-reuse

# With Anthropic API key
export ANTHROPIC_API_KEY=sk-...
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline
```

**Note:** `--live` is required. There is no dry-run mode — this benchmark makes real LLM calls.

## Output Structure

Each run creates a timestamped folder:

```
results/
  run_YYYYMMDD_HHMMSS_vX.Y.Z/
    CRM-pipeline_compose.json      # structured result
    CRM-hallucination_compose.json # pass rate summary
    CRM-reuse_compose.json         # token amortization data
    run_metadata.json              # reproducibility metadata
    benchmark_live.log             # full execution log
```

## Reproducibility

`run_metadata.json` captures bricks version, Python version, timestamp, model, git commit, and scenarios run.
