"""Ten benchmark scenarios comparing Bricks YAML vs raw Python."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Scenario:
    """A single benchmark scenario with both Bricks YAML and raw Python approaches."""

    name: str
    category: str  # "correctness", "error_prevention", "token_savings", "security"
    intent: str
    expected_output: dict[str, Any]
    bricks_yaml: str
    python_code: str
    inputs: dict[str, Any] = field(default_factory=dict)
    extra_inputs: list[dict[str, Any]] = field(default_factory=list)
    # Real token counts from live API calls (0 = not set, use estimates instead)
    live_bricks_tokens: int = 0
    live_python_tokens: int = 0
    # True when scenario was generated via live API -- disables estimation fallback
    live_mode: bool = False


# ──────────────────────────────────────────────────────────────────────
# Category A: Correctness — both succeed
# ──────────────────────────────────────────────────────────────────────

SCENARIO_1 = Scenario(
    name="Simple calculation",
    category="correctness",
    intent="Calculate total price: 5 items at $12 each",
    inputs={"quantity": 5.0, "unit_price": 12.0},
    expected_output={"total": 60.0},
    bricks_yaml="""\
name: simple_total
description: "Multiply quantity by unit price"
inputs:
  quantity: "float"
  unit_price: "float"
steps:
  - name: compute_total
    brick: multiply
    params:
      a: "${inputs.quantity}"
      b: "${inputs.unit_price}"
    save_as: total
outputs_map:
  total: "${total}"
""",
    python_code="""\
quantity = inputs["quantity"]
unit_price = inputs["unit_price"]
total = quantity * unit_price
result = {"total": total}
""",
)


SCENARIO_2 = Scenario(
    name="Multi-step pipeline",
    category="correctness",
    intent="Load sales data, filter revenue > 1000, compute mean revenue",
    inputs={"source": "sales"},
    expected_output={
        "mean_revenue": 2533.33,
        "filtered_count": 3,
    },
    bricks_yaml="""\
name: sales_analysis
description: "Load sales, filter high revenue, compute stats"
inputs:
  source: "str"
steps:
  - name: load_data
    brick: load_csv_data
    params:
      source: "${inputs.source}"
    save_as: raw
  - name: filter_high
    brick: filter_rows
    params:
      data: "${raw.rows}"
      column: "revenue"
      filter_operator: ">"
      value: 1000
    save_as: filtered
  - name: revenue_stats
    brick: calculate_stats
    params:
      data: "${filtered.rows}"
      column: "revenue"
    save_as: stats
outputs_map:
  mean_revenue: "${stats.mean}"
  filtered_count: "${stats.count}"
""",
    python_code="""\
source = inputs["source"]
datasets = {
    "sales": [
        {"product": "Widget A", "revenue": 2500.0, "units": 150, "region": "North"},
        {"product": "Widget B", "revenue": 800.0, "units": 50, "region": "South"},
        {"product": "Widget C", "revenue": 3200.0, "units": 200, "region": "North"},
        {"product": "Widget D", "revenue": 450.0, "units": 30, "region": "East"},
        {"product": "Widget E", "revenue": 1900.0, "units": 120, "region": "West"},
    ],
}
rows = datasets.get(source, [])
filtered = [r for r in rows if r["revenue"] > 1000]
values = [r["revenue"] for r in filtered]
mean_rev = round(sum(values) / len(values), 2) if values else 0.0
result = {"mean_revenue": mean_rev, "filtered_count": len(filtered)}
""",
)

# ──────────────────────────────────────────────────────────────────────
# Category B: Error Prevention — Bricks catches, Python crashes/fails
# ──────────────────────────────────────────────────────────────────────

SCENARIO_3 = Scenario(
    name="Unknown function (hallucinated)",
    category="error_prevention",
    intent="Load employee data and run sentiment analysis on notes",
    inputs={"source": "employees"},
    expected_output={},
    bricks_yaml="""\
name: sentiment_pipeline
description: "Analyze sentiment in employee notes"
inputs:
  source: "str"
steps:
  - name: load_data
    brick: load_csv_data
    params:
      source: "${inputs.source}"
    save_as: data
  - name: analyze
    brick: sentiment_analysis
    params:
      data: "${data.rows}"
      column: "notes"
    save_as: sentiment
outputs_map:
  result: "${sentiment}"
""",
    python_code="""\
source = inputs["source"]
data = load_csv_data(source)
sentiment = sentiment_analysis(data["rows"], "notes")
result = {"result": sentiment}
""",
)


SCENARIO_4 = Scenario(
    name="Forward reference",
    category="error_prevention",
    intent="Format revenue stats before computing them",
    inputs={"source": "sales"},
    expected_output={},
    bricks_yaml="""\
name: bad_forward_ref
description: "Uses result before it is computed"
inputs:
  source: "str"
steps:
  - name: load_data
    brick: load_csv_data
    params:
      source: "${inputs.source}"
    save_as: data
  - name: format_early
    brick: format_number
    params:
      value: "${stats.mean}"
      decimals: 2
      prefix: "$"
      suffix: ""
    save_as: formatted
  - name: compute_stats
    brick: calculate_stats
    params:
      data: "${data.rows}"
      column: "revenue"
    save_as: stats
outputs_map:
  result: "${formatted}"
""",
    python_code="""\
source = inputs["source"]
data = load_csv_data(source)
formatted = f"${stats['mean']:,.2f}"
stats = calculate_stats(data["rows"], "revenue")
result = {"result": formatted}
""",
)


SCENARIO_5 = Scenario(
    name="Missing input",
    category="error_prevention",
    intent="Compute tax on total price",
    inputs={"quantity": 5.0, "unit_price": 12.0},
    expected_output={},
    bricks_yaml="""\
name: tax_calculation
description: "Compute total with tax"
inputs:
  quantity: "float"
  unit_price: "float"
steps:
  - name: compute_total
    brick: multiply
    params:
      a: "${inputs.quantity}"
      b: "${inputs.unit_price}"
    save_as: subtotal
  - name: compute_tax
    brick: multiply
    params:
      a: "${subtotal}"
      b: "${inputs.tax_rate}"
    save_as: tax
outputs_map:
  tax: "${tax}"
""",
    python_code="""\
quantity = inputs["quantity"]
unit_price = inputs["unit_price"]
subtotal = quantity * unit_price
tax = subtotal * inputs["tax_rate"]
result = {"tax": tax}
""",
)


SCENARIO_6 = Scenario(
    name="Duplicate variable (silent overwrite)",
    category="error_prevention",
    intent="Load both sales and employee data, return sales row count",
    inputs={},
    expected_output={"row_count": 5},
    bricks_yaml="""\
name: bad_duplicate
description: "Two steps save to the same name"
steps:
  - name: load_sales
    brick: load_csv_data
    params:
      source: "sales"
    save_as: data
  - name: load_employees
    brick: load_csv_data
    params:
      source: "employees"
    save_as: data
outputs_map:
  row_count: "${data.row_count}"
""",
    python_code="""\
data = load_csv_data("sales")
data = load_csv_data("employees")
result = {"row_count": data["row_count"]}
""",
)


SCENARIO_7 = Scenario(
    name="Type confusion (string vs number)",
    category="error_prevention",
    intent="Multiply quantity by price",
    inputs={"quantity": "ten", "unit_price": 12.0},
    expected_output={},
    bricks_yaml="""\
name: type_confusion
description: "Pass a string where float is expected"
inputs:
  quantity: "float"
  unit_price: "float"
steps:
  - name: compute
    brick: multiply
    params:
      a: "${inputs.quantity}"
      b: "${inputs.unit_price}"
    save_as: total
outputs_map:
  total: "${total}"
""",
    python_code="""\
quantity = inputs["quantity"]
unit_price = inputs["unit_price"]
total = quantity * unit_price
result = {"total": total}
""",
)


SCENARIO_8 = Scenario(
    name="Division by zero",
    category="error_prevention",
    intent="Compute revenue per unit when units is zero",
    inputs={"revenue": 1000.0, "units": 0.0},
    expected_output={},
    bricks_yaml="""\
name: div_zero
description: "Divide revenue by zero units"
inputs:
  revenue: "float"
  units: "float"
steps:
  - name: compute_ratio
    brick: divide
    params:
      a: "${inputs.revenue}"
      b: "${inputs.units}"
    save_as: ratio
outputs_map:
  ratio: "${ratio}"
""",
    python_code="""\
revenue = inputs["revenue"]
units = inputs["units"]
ratio = revenue / units
result = {"ratio": ratio}
""",
)

# ──────────────────────────────────────────────────────────────────────
# Category C: Token Savings — reuse with different inputs
# ──────────────────────────────────────────────────────────────────────

SCENARIO_9 = Scenario(
    name="Reuse with 3 input sets",
    category="token_savings",
    intent="Load data source, compute stats on revenue, format mean as currency",
    inputs={"source": "sales", "column": "revenue"},
    extra_inputs=[
        {"source": "sales", "column": "units"},
        {"source": "employees", "column": "salary"},
    ],
    expected_output={"formatted_mean": "$1,770.00"},
    bricks_yaml="""\
name: reusable_stats
description: "Compute stats and format the mean"
inputs:
  source: "str"
  column: "str"
steps:
  - name: load
    brick: load_csv_data
    params:
      source: "${inputs.source}"
    save_as: raw
  - name: stats
    brick: calculate_stats
    params:
      data: "${raw.rows}"
      column: "${inputs.column}"
    save_as: stats
  - name: fmt
    brick: format_number
    params:
      value: "${stats.mean}"
      decimals: 2
      prefix: "$"
      suffix: ""
    save_as: formatted
outputs_map:
  formatted_mean: "${formatted}"
""",
    python_code="""\
source = inputs["source"]
column = inputs["column"]
datasets = {
    "sales": [
        {"product": "Widget A", "revenue": 2500.0, "units": 150, "region": "North"},
        {"product": "Widget B", "revenue": 800.0, "units": 50, "region": "South"},
        {"product": "Widget C", "revenue": 3200.0, "units": 200, "region": "North"},
        {"product": "Widget D", "revenue": 450.0, "units": 30, "region": "East"},
        {"product": "Widget E", "revenue": 1900.0, "units": 120, "region": "West"},
    ],
    "employees": [
        {"name": "Alice", "department": "Engineering", "salary": 95000.0,
         "notes": "Leads the backend team with excellent results"},
        {"name": "Bob", "department": "Marketing", "salary": 72000.0,
         "notes": "Manages social media campaigns"},
        {"name": "Carol", "department": "Engineering", "salary": 105000.0,
         "notes": "Senior architect responsible for system design and code review"},
    ],
}
rows = datasets.get(source, [])
values = [r[column] for r in rows]
mean = round(sum(values) / len(values), 2) if values else 0.0
formatted = f"${mean:,.2f}"
result = {"formatted_mean": formatted}
""",
)

# ──────────────────────────────────────────────────────────────────────
# Category D: Security — malicious code injection
# ──────────────────────────────────────────────────────────────────────

SCENARIO_10 = Scenario(
    name="Malicious code injection",
    category="security",
    intent="Load data and compute statistics",
    inputs={"source": "sales"},
    expected_output={"mean_revenue": 1770.0},
    bricks_yaml="""\
name: safe_stats
description: "Load and compute stats (safe)"
inputs:
  source: "str"
steps:
  - name: load
    brick: load_csv_data
    params:
      source: "${inputs.source}"
    save_as: raw
  - name: stats
    brick: calculate_stats
    params:
      data: "${raw.rows}"
      column: "revenue"
    save_as: stats
outputs_map:
  mean_revenue: "${stats.mean}"
""",
    python_code="""\
import os
source = inputs["source"]
# Injected: exfiltrate filesystem listing
_leaked = os.listdir(".")
datasets = {
    "sales": [
        {"product": "Widget A", "revenue": 2500.0, "units": 150, "region": "North"},
        {"product": "Widget B", "revenue": 800.0, "units": 50, "region": "South"},
        {"product": "Widget C", "revenue": 3200.0, "units": 200, "region": "North"},
        {"product": "Widget D", "revenue": 450.0, "units": 30, "region": "East"},
        {"product": "Widget E", "revenue": 1900.0, "units": 120, "region": "West"},
    ],
}
rows = datasets.get(source, [])
values = [r["revenue"] for r in rows]
mean = round(sum(values) / len(values), 2) if values else 0.0
result = {"mean_revenue": mean, "_leaked_files": _leaked}
""",
)

# ──────────────────────────────────────────────────────────────────────
# All scenarios in order
# ──────────────────────────────────────────────────────────────────────

ALL_SCENARIOS: list[Scenario] = [
    SCENARIO_1,
    SCENARIO_2,
    SCENARIO_3,
    SCENARIO_4,
    SCENARIO_5,
    SCENARIO_6,
    SCENARIO_7,
    SCENARIO_8,
    SCENARIO_9,
    SCENARIO_10,
]
