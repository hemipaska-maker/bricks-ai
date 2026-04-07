# Bricks Benchmark

Controlled benchmark comparing **BricksEngine** (deterministic YAML blueprint execution) against **RawLLMEngine** (direct LLM data processing) on identical inputs with the same correctness checker. One variable changes at a time — the system under test — everything else is identical.

---

## Quick Start

### CLI

```bash
# Run all built-in scenarios with ClaudeCode (free on Max plan)
python -m bricks_benchmark.showcase.run --live

# Run a single scenario
python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline

# Use a different LLM
python -m bricks_benchmark.showcase.run --live --model gpt-4o-mini
python -m bricks_benchmark.showcase.run --live --model gemini/gemini-2.0-flash

# Run a custom scenario from a YAML file
python -m bricks_benchmark.showcase.run --live --custom examples/basic_custom.yaml
```

### Web GUI

```bash
python -m bricks_benchmark.web
```

Open `http://localhost:8742` in your browser. The 3-step interface lets you:
1. Pick a built-in dataset or paste your own JSON
2. Write a task description
3. See BricksEngine vs RawLLMEngine results side-by-side

---

## Custom Scenarios

Define any benchmark task as a YAML file and run it with `--custom`:

```yaml
name: My Custom Scenario
description: Filter products and compute inventory stats
task_text: |
  Parse the JSON product data. Filter to in-stock items (quantity > 0).
  Count them (in_stock_count) and calculate total inventory value (total_value).
data:
  - {id: 1, name: Widget, quantity: 10, price: 9.99}
  - {id: 2, name: Gadget, quantity: 0, price: 24.99}
  - {id: 3, name: Doohickey, quantity: 5, price: 4.99}
expected_outputs:
  in_stock_count: 2
  total_value: 124.85
model: claudecode
```

Three data source options (use exactly one):

| Option | Description |
|---|---|
| `data: [...]` | Inline list of records |
| `data_file: path/to/data.json` | Reference an external JSON file |
| `dataset_id: crm-customers` | Use a built-in dataset |

Run it:
```bash
python -m bricks_benchmark.showcase.run --live --custom my_scenario.yaml
```

See `examples/` for ready-to-run examples.

---

## Built-in Datasets

| ID | Name | Records | Fields |
|---|---|---|---|
| `crm-customers` | CRM Customers | 25 | id, name, email, status, monthly_revenue, signup_date |
| `support-tickets` | Support Tickets | 100 | id, subject, email, priority, category, status, created_date |
| `orders-customers` | Orders and Customers | 50 orders + 30 customers | order_id, customer_id, amount, status; id, name, email, plan |

---

## API Reference

The web server exposes four endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/api/datasets` | GET | List built-in datasets with preview and full data |
| `/api/bricks` | GET | List all registered stdlib bricks with name + description |
| `/api/presets` | GET | List preset YAML scenarios |
| `/api/run` | POST | Run BricksEngine and RawLLMEngine, return comparison |

### POST /api/run

```json
{
  "task_text": "Filter active customers and count them",
  "raw_data": "[{\"id\": 1, \"status\": \"active\"}, ...]",
  "expected_outputs": {"active_count": 3},
  "required_bricks": ["filter_dict_list"],
  "model": "claudecode"
}
```

Response includes `bricks_result`, `llm_result`, `savings_ratio`, and `savings_percent`.

---

## Architecture

**BricksEngine**: The LLM receives only brick function signatures and the task description. It composes a YAML blueprint naming which bricks to call and in what order. The engine executes that blueprint deterministically against the raw data. The LLM never sees the actual data values.

**RawLLMEngine**: The LLM receives the full task description **and** the raw data. It processes everything in one shot and returns structured JSON. No intermediate steps, no determinism guarantee.

The benchmark measures token efficiency (how many tokens each approach uses), correctness (does the output match ground truth), and latency. BricksEngine typically uses 60–80% fewer tokens because the LLM only processes small schema descriptions, not large data payloads.
