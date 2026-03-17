"""Scenario A: Complexity curve — 3, 6, and 12 steps on the same domain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.showcase.scenarios import CODEGEN_SYSTEM
from benchmark.showcase.tokens import count_tokens

_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

# ── A-3: Room Area (3 steps) ──────────────────────────────────────────────────

_CODEGEN_USER_A3 = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {'result': float}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {'result': float}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {'display': str}.\"\"\"

Task: Write `calculate_room_area(width: float, height: float) -> dict` that
calls multiply(), round_value(), and format_result() to compute room area,
round to 2dp, and return {'area': float, 'display': str}.
Include type hints, docstring, and error handling for non-positive inputs.
"""

_GENERATED_CODE_A3 = '''\
def calculate_room_area(width: float, height: float) -> dict:
    """Calculate room area, round to 2dp, and return with a display string.

    Args:
        width: Room width in metres. Must be positive.
        height: Room height in metres. Must be positive.

    Returns:
        dict with 'area' (float) and 'display' (str).

    Raises:
        ValueError: If width or height is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive, got {width=}, {height=}")
    area_result = multiply(width, height)["result"]
    rounded = round_value(area_result, 2)["result"]
    display = format_result("Area (m2)", rounded)["display"]
    return {"area": rounded, "display": display}
'''

_BRICK_SCHEMAS_A3 = [
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
        "name": "format_result",
        "description": "Format a labelled result as display string.",
        "parameters": {"label": "str", "value": "float"},
        "returns": {"display": "str"},
    },
]

_INTENT_A3 = "Calculate room area for width * height, round to 2dp, format as display string."

# ── A-6: Property Price (6 steps) ────────────────────────────────────────────

_CODEGEN_USER_A6 = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {'result': float}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {'result': float}.\"\"\"

def add(a: float, b: float) -> dict:
    \"\"\"Add two numbers. Returns {'result': float}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {'display': str}.\"\"\"

Task: Write `calculate_property_price(width: float, height: float,
price_per_sqm: float, tax_rate: float) -> dict` that:
1. Computes area = width * height, rounded to 2dp
2. Computes base_price = area * price_per_sqm
3. Computes tax_amount = base_price * tax_rate
4. Computes total = base_price + tax_amount
5. Formats total as a display string labelled "Total (EUR)"
Returns {'total': float, 'display': str}.
Include type hints, docstring, and error handling for non-positive dimensions.
"""

_GENERATED_CODE_A6 = '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Calculate property price including tax from room dimensions.

    Args:
        width: Room width in metres. Must be positive.
        height: Room height in metres. Must be positive.
        price_per_sqm: Price per square metre in EUR.
        tax_rate: Tax rate as a decimal (e.g. 0.17 for 17%).

    Returns:
        dict with 'total' (float) and 'display' (str).

    Raises:
        ValueError: If width or height is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive, got {width=}, {height=}")
    area_result = multiply(width, height)["result"]
    rounded_area = round_value(area_result, 2)["result"]
    base_price = multiply(rounded_area, price_per_sqm)["result"]
    tax_amount = multiply(base_price, tax_rate)["result"]
    total = add(base_price, tax_amount)["result"]
    display = format_result("Total (EUR)", total)["display"]
    return {"total": total, "display": display}
'''

_BRICK_SCHEMAS_A6 = [
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

_INTENT_A6 = (
    "Calculate property price: compute area from width * height, round to 2dp, "
    "multiply by price_per_sqm for base_price, multiply base_price by tax_rate for tax, "
    "add base_price + tax for total, format total as display string."
)

# ── A-12: Full Property Valuation (12 steps) ──────────────────────────────────

_CODEGEN_USER_A12 = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {'result': float}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {'result': float}.\"\"\"

def add(a: float, b: float) -> dict:
    \"\"\"Add two numbers. Returns {'result': float}.\"\"\"

def subtract(a: float, b: float) -> dict:
    \"\"\"Subtract b from a. Returns {'result': float}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {'display': str}.\"\"\"

Task: Write `calculate_property_valuation(width: float, height: float,
price_per_sqm: float, discount_rate: float, tax_rate: float,
monthly_factor: float) -> dict` that:
1. Computes area = width * height, rounded to 2dp
2. Computes base_price = area * price_per_sqm
3. Computes discount_amount = base_price * discount_rate
4. Computes net_price = base_price - discount_amount
5. Computes tax_amount = net_price * tax_rate
6. Computes total = net_price + tax_amount, rounded to 2dp
7. Computes monthly = total * monthly_factor, rounded to 2dp
8. Formats total as "Total: X" and monthly as "Monthly: X"
Returns {'total': float, 'monthly': float, 'total_display': str, 'monthly_display': str}.
Include type hints, docstring, and error handling.
"""

_GENERATED_CODE_A12 = '''\
def calculate_property_valuation(
    width: float,
    height: float,
    price_per_sqm: float,
    discount_rate: float,
    tax_rate: float,
    monthly_factor: float,
) -> dict:
    """Calculate full property valuation with discount, tax, and monthly payment.

    Args:
        width: Room width in metres. Must be positive.
        height: Room height in metres. Must be positive.
        price_per_sqm: Price per square metre in EUR.
        discount_rate: Discount rate as a decimal (e.g. 0.10 for 10%).
        tax_rate: Tax rate as a decimal (e.g. 0.17 for 17%).
        monthly_factor: Monthly payment factor (e.g. 0.0045).

    Returns:
        dict with 'total', 'monthly', 'total_display', 'monthly_display'.

    Raises:
        ValueError: If width or height is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive, got {width=}, {height=}")
    area_raw = multiply(width, height)["result"]
    area = round_value(area_raw, 2)["result"]
    base_price = multiply(area, price_per_sqm)["result"]
    discount_amount = multiply(base_price, discount_rate)["result"]
    net_price = subtract(base_price, discount_amount)["result"]
    tax_amount = multiply(net_price, tax_rate)["result"]
    total_raw = add(net_price, tax_amount)["result"]
    total = round_value(total_raw, 2)["result"]
    monthly_raw = multiply(total, monthly_factor)["result"]
    monthly = round_value(monthly_raw, 2)["result"]
    total_display = format_result("Total", total)["display"]
    monthly_display = format_result("Monthly", monthly)["display"]
    return {
        "total": total,
        "monthly": monthly,
        "total_display": total_display,
        "monthly_display": monthly_display,
    }
'''

_BRICK_SCHEMAS_A12 = [
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
        "name": "subtract",
        "description": "Subtract b from a.",
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

_INTENT_A12 = (
    "Calculate full property valuation: compute area from dimensions, apply price per sqm, "
    "apply discount, compute tax on net price, calculate total and monthly payment, "
    "format both total and monthly as display strings."
)

# ── Shared live intents ───────────────────────────────────────────────────────

INTENT_A3 = _INTENT_A3
INTENT_A6 = _INTENT_A6
INTENT_A12 = _INTENT_A12

# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_registry_a3() -> object:
    """Build registry for A-3 (multiply, round_value, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, format_result)


def _build_registry_a6() -> object:
    """Build registry for A-6 (multiply, round_value, add, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


def _build_registry_a12() -> object:
    """Build registry for A-12 (multiply, round_value, add, subtract, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value, subtract
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, subtract, format_result)


def _execute_blueprint(blueprint_file: str, inputs: dict[str, Any], registry: object) -> dict[str, Any]:
    """Load and run a blueprint through the Bricks engine."""
    from bricks.core import BlueprintEngine, BlueprintLoader

    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry)  # type: ignore[arg-type]
    yaml_str = (_BLUEPRINTS / blueprint_file).read_text()
    sequence = loader.load_string(yaml_str)
    return engine.run(sequence, inputs=inputs).outputs


# ── A-3 public functions ──────────────────────────────────────────────────────


def code_generation_a3() -> dict[str, Any]:
    """Return token cost for A-3 code generation (3-step room area)."""
    prompt = CODEGEN_SYSTEM + "\n\n" + _CODEGEN_USER_A3
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(_GENERATED_CODE_A3)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "code": _GENERATED_CODE_A3,
    }


def bricks_a3() -> dict[str, Any]:
    """Return token cost and execute A-3 Blueprint (3-step room area)."""
    schema_payload = json.dumps(_BRICK_SCHEMAS_A3, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "room_area.yaml").read_text()
    prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {_INTENT_A3}"
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(blueprint_yaml)
    result = _execute_blueprint("room_area.yaml", {"width": 7.5, "height": 4.2}, _build_registry_a3())
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "blueprint": blueprint_yaml,
        "execution_result": result,
    }


# ── A-6 public functions ──────────────────────────────────────────────────────


def code_generation_a6() -> dict[str, Any]:
    """Return token cost for A-6 code generation (6-step property price)."""
    prompt = CODEGEN_SYSTEM + "\n\n" + _CODEGEN_USER_A6
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(_GENERATED_CODE_A6)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "code": _GENERATED_CODE_A6,
    }


def bricks_a6() -> dict[str, Any]:
    """Return token cost and execute A-6 Blueprint (6-step property price)."""
    schema_payload = json.dumps(_BRICK_SCHEMAS_A6, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "property_price.yaml").read_text()
    prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {_INTENT_A6}"
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(blueprint_yaml)
    result = _execute_blueprint(
        "property_price.yaml",
        {"width": 7.5, "height": 4.2, "price_per_sqm": 3500.0, "tax_rate": 0.17},
        _build_registry_a6(),
    )
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "blueprint": blueprint_yaml,
        "execution_result": result,
    }


# ── A-12 public functions ─────────────────────────────────────────────────────


def code_generation_a12() -> dict[str, Any]:
    """Return token cost for A-12 code generation (12-step property valuation)."""
    prompt = CODEGEN_SYSTEM + "\n\n" + _CODEGEN_USER_A12
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(_GENERATED_CODE_A12)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "code": _GENERATED_CODE_A12,
    }


def bricks_a12() -> dict[str, Any]:
    """Return token cost and execute A-12 Blueprint (12-step property valuation)."""
    schema_payload = json.dumps(_BRICK_SCHEMAS_A12, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "property_valuation.yaml").read_text()
    prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {_INTENT_A12}"
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(blueprint_yaml)
    result = _execute_blueprint(
        "property_valuation.yaml",
        {
            "width": 7.5,
            "height": 4.2,
            "price_per_sqm": 3500.0,
            "discount_rate": 0.10,
            "tax_rate": 0.17,
            "monthly_factor": 0.0045,
        },
        _build_registry_a12(),
    )
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "blueprint": blueprint_yaml,
        "execution_result": result,
    }


# ── Public API ────────────────────────────────────────────────────────────────


def run_complexity_curve() -> list[dict[str, Any]]:
    """Run all three sub-scenarios and return complexity curve data.

    Returns:
        List of dicts, one per sub-scenario, each containing
        ``label``, ``steps``, ``codegen_tokens``, ``bricks_tokens``.
    """
    results = []
    for label, steps, fn_cg, fn_br in [
        ("A-3", 3, code_generation_a3, bricks_a3),
        ("A-6", 6, code_generation_a6, bricks_a6),
        ("A-12", 12, code_generation_a12, bricks_a12),
    ]:
        cg = fn_cg()
        br = fn_br()
        results.append(
            {
                "label": label,
                "steps": steps,
                "codegen_tokens": cg["total_tokens"],
                "bricks_tokens": br["total_tokens"],
            }
        )
    return results
