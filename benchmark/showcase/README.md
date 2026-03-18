# Bricks Benchmark: Apples-to-Apples

> Same agent, same task, same model, same system prompt. The only variable: whether Bricks MCP tools are available.

## How It Works

No actual MCP server is required. Tool responses are served locally using the real Bricks engine:

```
No-tools mode:  Task -> Claude (no tools) -> writes Python code
Bricks mode:    Task -> Claude + {list_bricks, lookup_brick, execute_blueprint}
                     -> discovers bricks -> composes Blueprint YAML -> executes
```

Both modes receive the identical `APPLES_SYSTEM` prompt and the identical task string. Token counts include **all turns** (tool calls, tool results, continuations).

## Scenarios

| Scenario | Description |
|---|---|
| **A2: Complexity Curve** | Same 3 tasks (3/6/12 steps) — no_tools writes code, bricks composes+executes Blueprint |
| **C2: Reuse Economics** | A2-6 task x 10 runs — no_tools regenerates code each time, bricks reuses Blueprint (0 tokens runs 2-10) |
| **D2: Determinism** | A2-6 task x 5 identical runs — compare code variability vs Blueprint consistency |

## Run It Yourself

```bash
# From the project root
pip install -e ".[ai,benchmark]"
export ANTHROPIC_API_KEY=your-key-here

# Run everything
python -m benchmark.showcase.run --live

# Run a single scenario
python -m benchmark.showcase.run --live --scenario A2
python -m benchmark.showcase.run --live --scenario C2
python -m benchmark.showcase.run --live --scenario D2

# Run a single sub-scenario (saves tokens!)
python -m benchmark.showcase.run --live --scenario A2-3
python -m benchmark.showcase.run --live --scenario A2-6
python -m benchmark.showcase.run --live --scenario A2-12

# Run multiple scenarios
python -m benchmark.showcase.run --live --scenario A2-3 --scenario C2

# Custom output directory
python -m benchmark.showcase.run --live --output-dir /tmp/my-results
```

**Note:** `--live` is required. There is no estimated mode — this benchmark makes real API calls.

## Example Output

```
Bricks v0.4.3
Run folder: benchmark/showcase/results/run_20260318_143022_v0.4.3
Scenarios: A2-3, A2-6, A2-12, C2, D2

  [A2-3] Running...
  [A2-3] Turn 1/no_tools: 847 input + 560 output = 1,407 tokens (1.2s)
  [A2-3] Turn 1/bricks: 1,203 input + 892 output = 2,095 tokens (1.8s)
  [A2-3] Turn 2/bricks: tool_call list_bricks -> 12 bricks found (0.3s)
  [A2-3] Turn 3/bricks: tool_call execute_blueprint -> success (0.5s)
  [A2-3] done  no_tools=1,407  bricks=4,190  (3.0x)

  +----------+------------+------------+--------+--------------+
  | Task     | No Tools   | Bricks     | Ratio  | Bricks turns |
  +----------+------------+------------+--------+--------------+
  | A2-3     |      1,407 |      4,190 |   3.0x |            3 |
  | A2-6     |      1,638 |      8,201 |   5.0x |            4 |
  | A2-12    |      1,746 |     12,350 |   7.1x |            5 |
  +----------+------------+------------+--------+--------------+

  [C2] Running (10 runs)...
  [C2] done  no_tools=16,380  bricks=8,201  (2.0x)

  [D2] Running (5 runs)...
  [D2] done  unique_codes=5/5  unique_blueprints=1/5

  Total: 47,532 tokens used (input: 31,200 + output: 16,332)
  Estimated cost: ~$0.023 (claude-haiku-4-5-20251001)
  Elapsed: 42.3s
```

## Output Structure

Each run creates a timestamped folder:

```
results/
  run_YYYYMMDD_HHMMSS_vX.Y.Z/
    apples_to_apples/
      results.json        # machine-readable comparison
      summary.md          # human-readable report
      A2_complexity.json  # per-scenario detail
      C2_reuse.json
      D2_determinism.json
    run_metadata.json     # reproducibility metadata
    benchmark_live.log    # full execution log
```

## Reproducibility

`run_metadata.json` captures everything needed to reproduce a run:

```json
{
    "bricks_version": "0.4.3",
    "python_version": "3.10.12",
    "timestamp": "2026-03-18T14:30:22",
    "ai_model": "claude-haiku-4-5-20251001",
    "ai_provider": "anthropic",
    "anthropic_sdk_version": "0.45.0",
    "mode": "live",
    "command": "python -m benchmark.showcase.run --live",
    "scenarios_run": ["A2-3", "A2-6", "A2-12", "C2", "D2"],
    "os": "Windows 10.0",
    "git_commit": "abc1234",
    "git_branch": "development",
    "git_dirty": false
}
```
