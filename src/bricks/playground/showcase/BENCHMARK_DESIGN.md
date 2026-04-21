# Bricks CRM Benchmark Design

> Controlled comparison: same input, same checker, swap only the system under test.

## Design Philosophy

This benchmark follows the controlled benchmarking methodology used by MLPerf, HumanEval, and Stanford HELM: **one variable at a time**.

Both engines receive **identical input**. Both are evaluated with **identical checker** (`check_correctness()` with float tolerance). Only the system under test changes.

This makes the comparison immediately credible — users don't need to dig into code to trust the numbers.

## Unified Pipeline

```
                 ┌─────────────────────────┐
                 │    generate_crm_task()   │
                 │  seed → 50 CRM records   │
                 └──────────┬──────────────┘
                            │
                 ┌──────────┴──────────────┐
                 │  task_text              │
                 │  raw_api_response (JSON)│
                 │  expected_outputs       │
                 └──────────┬──────────────┘
                            │
             ┌──────────────┴──────────────┐
             │      SAME INPUT TO BOTH     │
             │   task_text + raw_api_data   │
             └──────┬──────────────┬───────┘
                    │              │
       ┌────────────┘              └────────────┐
       ▼                                        ▼
┌──────────────────┐                 ┌──────────────────┐
│   BricksEngine   │                 │   RawLLMEngine   │
│                  │                 │                  │
│ compose(task) →  │                 │ LLM(task+data) → │
│ load(yaml) →     │                 │ parse JSON →     │
│ execute(data) →  │                 │ return dict      │
│ return dict      │                 │                  │
└────────┬─────────┘                 └────────┬─────────┘
         │                                    │
         │  ┌──────────────────────────┐      │
         └─►│  SAME EngineResult shape │◄─────┘
            │  outputs: dict           │
            │  tokens, duration, model │
            └────────────┬─────────────┘
                         │
            ┌────────────▼─────────────┐
            │   SAME CHECKER           │
            │   check_correctness(     │
            │     actual, expected,    │
            │     float_tolerance)     │
            └────────────┬─────────────┘
                         │
            ┌────────────▼─────────────┐
            │   SAME BenchmarkResult   │
            │   engine, outputs,       │
            │   correct, tokens,       │
            │   duration, raw_response │
            └──────────────────────────┘
```

## Engine Implementations

### BricksEngine

1. `compose(task_text, registry)` — LLM generates YAML blueprint from task + brick catalog
2. `load(blueprint_yaml)` — parse YAML into Blueprint object
3. `execute(raw_data)` — run blueprint deterministically with actual data

The LLM only sees **brick signatures** during compose, not the raw data. The raw data flows in at execute time. This is why Bricks can reuse the same blueprint across different datasets (CRM-reuse scenario).

### RawLLMEngine

1. Build prompt: `task_text + raw_data + "return JSON only"`
2. `provider.complete(prompt)` — LLM reasons over everything at once
3. `json.loads(response)` — parse structured outputs

The LLM sees everything at once and must do mental arithmetic. JSON parse failures are handled gracefully (empty dict, logged at WARNING).

## Scenarios

| Scenario | What it proves | Runs | Metric | Expected outcome |
|----------|----------------|------|--------|-----------------|
| **CRM-pipeline** | Deterministic execution beats LLM reasoning | 1 each | Correct/Wrong per engine | Bricks ✓, LLM ✗ |
| **CRM-hallucination** | Bricks consistent at scale; LLMs hallucinate math | 10 each | Pass rate % | Bricks 10/10, LLM < 10 |
| **CRM-reuse** | Compose once, run forever at $0 | 1 compose + 19 reuse vs 20 LLM calls | Total tokens, pass rate | Bricks tokens ≈ N, LLM tokens ≈ 20×M |

## CRM Task Structure

Each task is generated deterministically from a seed:

```python
CRMTask(
    task_text="From the raw API response, compute: ...",
    raw_api_response="[{'id': 1, 'status': 'active', ...}, ...]",
    expected_outputs={
        "active_count": 18,
        "total_active_revenue": 3447.50,
        "avg_active_revenue": 191.53,
    },
    required_bricks=["parse_json", "filter_records", "count_items", ...]
)
```

## Result Display

Side-by-side table showing both engines' actual values vs expected:

```
  CRM-pipeline Results (seed=42)
  ──────────────────────────────────────────────────────────────────────
  Key                          BricksEngine         RawLLMEngine
  ──────────────────────────────────────────────────────────────────────
  active_count                       18 ✓                   17 ✗
  avg_active_revenue             191.53 ✓               188.24 ✗
  total_active_revenue           3447.5 ✓               3200.0 ✗
  ──────────────────────────────────────────────────────────────────────
  Correct                         YES ✓                    NO ✗
  Tokens (in/out)              2400/350                 3100/280
  Duration                         8.2s                     4.1s
  Model                   claude-sonnet-...      claude-sonnet-...
```

## Model Variance Note

Benchmark results depend on the model used for composition and baseline.
The reference results use `claude-haiku-4-5`. Other models may compose
different (but valid) blueprints, or produce different baseline accuracy.
When comparing runs, always check the `ai_model` field in `run_metadata.json`.

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...
python -m bricks.playground.showcase.run --live

# OpenAI
export OPENAI_API_KEY=sk-...
python -m bricks.playground.showcase.run --live --model gpt-4o-mini

# Google Gemini
export GOOGLE_API_KEY=AIza...
python -m bricks.playground.showcase.run --live --model gemini/gemini-2.0-flash

# Local with Ollama (free, no API key)
python -m bricks.playground.showcase.run --live --model ollama/llama3

# Claude Code Max plan ($0, no API key) — ClaudeCode composes, default model baselines
python -m bricks.playground.showcase.run --live --claudecode

# Mix: ClaudeCode compose + GPT baseline
python -m bricks.playground.showcase.run --live --claudecode --model gpt-4o-mini
```

## File Structure

```
showcase/
├── engine.py          # Engine ABC, EngineResult, BenchmarkResult, BricksEngine, RawLLMEngine
├── crm_scenario.py    # run_scenario(), run_crm_pipeline/hallucination/reuse
├── crm_generator.py   # CRMTask, generate_crm_task(seed)
├── run.py             # CLI entry point, instantiates both engines
├── result_writer.py   # check_correctness(), ScenarioResult models
├── formatters.py      # print_cost_summary(), estimate_cost()
└── BENCHMARK_DESIGN.md  # this file
```
