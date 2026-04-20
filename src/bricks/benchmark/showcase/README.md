# Bricks Benchmark

> Controlled comparison: BricksEngine vs RawLLMEngine on real-world data processing tasks.

## How It Works

Both engines receive **identical input** (task description + raw data) and are evaluated with the same `check_correctness()` function. Only the system under test changes.

```
BricksEngine:   task_text → BlueprintComposer → YAML → BlueprintEngine(raw_data) → outputs
RawLLMEngine:   task_text + raw_data → LLM(JSON prompt) → parse JSON → outputs
```

Any task that satisfies the `BenchmarkTask` protocol (task_text, raw_api_response, expected_outputs, required_bricks) plugs directly into the benchmark runner — no engine changes needed.

## Scenarios

| Scenario | Description |
|---|---|
| **CRM-pipeline** | 1 compose run on seed=42; check active_count, total_active_revenue, avg_active_revenue |
| **CRM-hallucination** | 10x runs (different seeds); compare pass rates across both engines |
| **CRM-reuse** | Compose blueprint once (seed=42), reuse for 19 more seeds; measure token amortization |
| **TICKET-pipeline** | 100 support tickets; validate emails, filter by priority, count by category |

## Run It

```bash
# All scenarios with ClaudeCode (free on Max plan)
python -m bricks.benchmark.showcase.run --live --model claudecode

# Specific scenario
python -m bricks.benchmark.showcase.run --live --model claudecode --scenario CRM-pipeline
python -m bricks.benchmark.showcase.run --live --model claudecode --scenario TICKET-pipeline

# With Anthropic API key
export ANTHROPIC_API_KEY=sk-...
python -m bricks.benchmark.showcase.run --live --scenario CRM-pipeline

# With any LLM via LiteLLM
python -m bricks.benchmark.showcase.run --live --model gpt-4o-mini
python -m bricks.benchmark.showcase.run --live --model gemini/gemini-2.0-flash
python -m bricks.benchmark.showcase.run --live --model ollama/llama3
```

**Note:** `--live` is required. This benchmark makes real LLM calls.

## Architecture

```
engine.py           # BenchmarkTask Protocol, Engine ABC, BricksEngine, RawLLMEngine
scenario_runner.py  # Shared run_scenario() — works with any BenchmarkTask
crm_generator.py    # CRM customer data generator (deterministic, seed-based)
crm_scenario.py     # CRM pipeline, hallucination, and reuse scenarios
ticket_generator.py # Support ticket data generator (100 tickets, PII, mixed emails)
ticket_scenario.py  # Ticket pipeline scenario
run.py              # CLI entry point, model routing, scenario expansion
result_writer.py    # check_correctness(), JSON result output
formatters.py       # Side-by-side comparison tables, cost summary
metadata.py         # Run directory creation, reproducibility metadata
registry_factory.py # Registry builder — assembles BrickRegistry for benchmark scenarios
```

## Output Structure

Each run creates a timestamped folder:

```
results/
  run_YYYYMMDD_HHMMSS_vX.Y.Z/
    CRM-pipeline_compose.json
    CRM-hallucination_compose.json
    CRM-reuse_compose.json
    run_metadata.json
    benchmark_live.log
```

## Reproducibility

`run_metadata.json` captures bricks version, Python version, timestamp, model, git commit, and scenarios run.

## Adding New Scenarios

1. Create a generator (e.g. `join_generator.py`) with a dataclass satisfying `BenchmarkTask`
2. Create a scenario runner (e.g. `join_scenario.py`) that calls `run_scenario()` from `scenario_runner.py`
3. Add the scenario name to `VALID_SCENARIOS` in `run.py` and wire the routing in `run_benchmark()`
