"""Scenario C: Reuse economics — 10 runs with A-6 Blueprint vs 10 code-gen calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.showcase.scenarios import CODEGEN_SYSTEM
from benchmark.showcase.tokens import count_tokens
from bricks.core import BlueprintEngine
from bricks.core.models import BlueprintDefinition

_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

# 10 property inputs for the A-6 blueprint
PROPERTY_INPUTS = [
    {"width": 7.5, "height": 4.2, "price_per_sqm": 3500.0, "tax_rate": 0.17},
    {"width": 5.0, "height": 3.0, "price_per_sqm": 4200.0, "tax_rate": 0.17},
    {"width": 10.0, "height": 8.0, "price_per_sqm": 2800.0, "tax_rate": 0.10},
    {"width": 6.5, "height": 4.0, "price_per_sqm": 5000.0, "tax_rate": 0.17},
    {"width": 3.5, "height": 3.5, "price_per_sqm": 6000.0, "tax_rate": 0.20},
    {"width": 12.0, "height": 6.0, "price_per_sqm": 3000.0, "tax_rate": 0.17},
    {"width": 4.0, "height": 4.0, "price_per_sqm": 4500.0, "tax_rate": 0.10},
    {"width": 8.0, "height": 5.5, "price_per_sqm": 3800.0, "tax_rate": 0.17},
    {"width": 9.0, "height": 7.0, "price_per_sqm": 2500.0, "tax_rate": 0.20},
    {"width": 6.0, "height": 3.0, "price_per_sqm": 5500.0, "tax_rate": 0.10},
]

# Code-gen prompt for A-6 task (same helper signatures, same task description)
_CODEGEN_USER_TEMPLATE = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {{'result': float}}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {{'result': float}}.\"\"\"

def add(a: float, b: float) -> dict:
    \"\"\"Add two numbers. Returns {{'result': float}}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {{'display': str}}.\"\"\"

Task: Write `calculate_property_price(width: float, height: float,
price_per_sqm: float, tax_rate: float) -> dict`.
Width={width}, Height={height}, PricePerSqm={price_per_sqm}, TaxRate={tax_rate}.
"""

_BRICK_SCHEMAS = [
    {
        "name": "multiply",
        "description": "Multiply two numbers.",
        "parameters": {"a": "float", "b": "float"},
        "returns": {"result": "float"},
    },
    {
        "name": "round_value",
        "description": "Round a float to decimal places.",
        "parameters": {"value": "float", "decimals": "int"},
        "returns": {"result": "float"},
    },
    {
        "name": "add",
        "description": "Add two numbers.",
        "parameters": {"a": "float", "b": "float"},
        "returns": {"result": "float"},
    },
    {
        "name": "format_result",
        "description": "Format a labelled result as display string.",
        "parameters": {"label": "str", "value": "float"},
        "returns": {"display": "str"},
    },
]

_SIMULATED_PYTHON_OUTPUT = '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Calculate property price including tax."""
    if width <= 0 or height <= 0:
        raise ValueError("Dimensions must be positive")
    area = round_value(multiply(width, height)["result"], 2)["result"]
    base_price = multiply(area, price_per_sqm)["result"]
    tax = multiply(base_price, tax_rate)["result"]
    total = add(base_price, tax)["result"]
    return {"total": total, "display": format_result("Total (EUR)", total)["display"]}
'''


def code_generation_approach() -> dict[str, Any]:
    """Return token cost for 10 separate code-gen calls (one per input set).

    Each call gets a new prompt with different property inputs — the LLM must
    regenerate the full 6-step function each time.
    """
    runs = []
    total_tokens = 0

    for i, inp in enumerate(PROPERTY_INPUTS):
        user_prompt = _CODEGEN_USER_TEMPLATE.format(**inp)
        prompt = CODEGEN_SYSTEM + "\n\n" + user_prompt
        prompt_tokens = count_tokens(prompt)
        output_tokens = count_tokens(_SIMULATED_PYTHON_OUTPUT)
        run_total = prompt_tokens + output_tokens
        total_tokens += run_total
        runs.append(
            {
                "run": i + 1,
                "inputs": inp,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": run_total,
            }
        )

    return {
        "runs": runs,
        "total_tokens": total_tokens,
        "per_run_avg": total_tokens // len(runs),
    }


def bricks_approach() -> dict[str, Any]:
    """Return token cost for 10 runs using the A-6 Blueprint.

    Run 1: one LLM call — brick schemas + intent → generates Blueprint YAML.
    Runs 2-10: ZERO LLM tokens — Blueprint stored and executed locally with
    different inputs. No re-generation, no API call.
    """
    schema_payload = json.dumps(_BRICK_SCHEMAS, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "property_price.yaml").read_text()

    intent = "Calculate property price: area from dimensions, base price, tax, total, format display."
    first_prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {intent}"
    first_prompt_tokens = count_tokens(first_prompt)
    first_output_tokens = count_tokens(blueprint_yaml)
    first_total = first_prompt_tokens + first_output_tokens

    runs = []
    total_tokens = first_total
    runs.append(
        {
            "run": 1,
            "inputs": PROPERTY_INPUTS[0],
            "prompt_tokens": first_prompt_tokens,
            "output_tokens": first_output_tokens,
            "total_tokens": first_total,
            "note": "LLM call: generate blueprint (one-time)",
        }
    )

    execution_results = []
    engine = _build_engine()
    blueprint_sequence = _load_sequence(blueprint_yaml)

    for i, inp in enumerate(PROPERTY_INPUTS):
        result = engine.run(blueprint_sequence, inputs=inp).outputs
        execution_results.append({"run": i + 1, "inputs": inp, "output": result})
        if i > 0:
            runs.append(
                {
                    "run": i + 1,
                    "inputs": inp,
                    "prompt_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "note": "engine execution (no LLM call, 0 tokens)",
                }
            )

    return {
        "runs": runs,
        "total_tokens": total_tokens,
        "per_run_avg": total_tokens // len(runs),
        "execution_results": execution_results,
    }


def _build_engine() -> BlueprintEngine:
    """Build a BlueprintEngine with math and string bricks registered."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    registry = build_showcase_registry(multiply, round_value, add, format_result)
    return BlueprintEngine(registry=registry)


def _load_sequence(yaml_str: str) -> BlueprintDefinition:
    """Load a BlueprintDefinition from a YAML string."""
    from bricks.core import BlueprintLoader

    return BlueprintLoader().load_string(yaml_str)
