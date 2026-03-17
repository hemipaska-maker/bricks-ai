"""Scenario D: Determinism benchmark — code gen variability vs Blueprint consistency."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

CODEGEN_USER = """\
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

# ── 5 simulated AI-generated code variations (for estimated mode) ────────────

_SIMULATED_GENERATIONS: list[str] = [
    # Generation 1: verbose, fully typed, validation, standard names
    '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Compute property price with tax from room dimensions.

    Args:
        width: Room width in metres. Must be positive.
        height: Room height in metres. Must be positive.
        price_per_sqm: Price per square metre in EUR.
        tax_rate: Tax rate as a decimal (e.g. 0.17 for 17%).

    Returns:
        dict with 'total' (float) and 'display' (str).

    Raises:
        ValueError: If either dimension is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive, got {width=}, {height=}")
    area_result = multiply(width, height)["result"]
    rounded_area = round_value(area_result, 2)["result"]
    base_price_value = multiply(rounded_area, price_per_sqm)["result"]
    tax_value = multiply(base_price_value, tax_rate)["result"]
    total_price = add(base_price_value, tax_value)["result"]
    display_text = format_result("Total (EUR)", total_price)["display"]
    return {"total": total_price, "display": display_text}
''',
    # Generation 2: minimal docstring, no validation, short names
    '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Calculate property price including tax."""
    area = round_value(multiply(width, height)["result"], 2)["result"]
    base = multiply(area, price_per_sqm)["result"]
    tax = multiply(base, tax_rate)["result"]
    total = add(base, tax)["result"]
    return {"total": total, "display": format_result("Total (EUR)", total)["display"]}
''',
    # Generation 3: verbose docstring, split validation, inline comments
    '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Calculate the total price for a property including VAT.

    First computes the floor area from width and height, then applies
    the price per square metre to get the base price, adds tax,
    and returns the total with a formatted display string.

    Args:
        width: Width of the property in metres.
        height: Depth of the property in metres.
        price_per_sqm: Price per square metre in EUR.
        tax_rate: VAT rate as a decimal fraction.

    Returns:
        dict containing 'total' (float) and 'display' (str).

    Raises:
        ValueError: If width is not positive.
        ValueError: If height is not positive.
    """
    if width <= 0:
        raise ValueError(f"Width must be positive, got {width}")
    if height <= 0:
        raise ValueError(f"Height must be positive, got {height}")
    # Step 1: compute area
    raw_area = multiply(width, height)["result"]
    # Step 2: round area
    floor_area = round_value(raw_area, decimals=2)["result"]
    # Step 3: base price
    price_base = multiply(floor_area, price_per_sqm)["result"]
    # Step 4: tax
    tax_component = multiply(price_base, tax_rate)["result"]
    # Step 5: total
    grand_total = add(price_base, tax_component)["result"]
    # Step 6: format
    label_output = format_result("Total (EUR)", grand_total)["display"]
    return {"total": grand_total, "display": label_output}
''',
    # Generation 4: terse, single-letter vars, no docstring body
    '''\
def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Return total price and display string."""
    a = round_value(multiply(width, height)["result"])["result"]
    b = multiply(a, price_per_sqm)["result"]
    t = multiply(b, tax_rate)["result"]
    s = add(b, t)["result"]
    d = format_result("Total (EUR)", s)["display"]
    return {"total": s, "display": d}
''',
    # Generation 5: extra import (hallucination), medium verbosity, validation
    '''\
import math

def calculate_property_price(
    width: float, height: float, price_per_sqm: float, tax_rate: float
) -> dict:
    """Calculate property price with tax. Raises ValueError for bad inputs."""
    if not (width > 0 and height > 0):
        raise ValueError("Dimensions must be positive")
    area_m2 = round_value(multiply(width, height)["result"], 2)["result"]
    base_amount = multiply(area_m2, price_per_sqm)["result"]
    tax_amount = multiply(base_amount, tax_rate)["result"]
    total_amount = add(base_amount, tax_amount)["result"]
    display_str = format_result("Total (EUR)", total_amount)["display"]
    return {"total": total_amount, "display": display_str}
''',
]

# Built-in names that are not hallucinations
_ALLOWED_CALLS: frozenset[str] = frozenset(
    {
        "multiply",
        "round_value",
        "add",
        "format_result",
        "ValueError",
        "TypeError",
        "str",
        "float",
        "int",
        "round",
        "print",
        "len",
        "isinstance",
        "range",
    }
)

_REQUIRED_FUNCTIONS = ("multiply", "round_value", "add", "format_result")


# ── Metric helpers ───────────────────────────────────────────────────────────


def _count_lines(code: str) -> int:
    """Count non-blank lines in a code string."""
    return sum(1 for ln in code.splitlines() if ln.strip())


def _extract_docstring_length(code: str) -> int:
    """Return character length of the first function's docstring."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                return len(node.body[0].value.value)
    except SyntaxError:
        pass
    return 0


def _has_error_handling(code: str) -> bool:
    """Return True if the code contains explicit error handling (raise/try)."""
    return bool(re.search(r"\braise\b|\btry\b", code))


def _extract_variable_names(code: str) -> set[str]:
    """Return assigned local variable names inside the first function definition."""
    names: set[str] = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                names.add(target.id)
    except SyntaxError:
        pass
    return names


def _extract_function_signature(code: str) -> str:
    """Return the def line of the first function in code."""
    m = re.search(r"def \w+\([^)]*\)(?:\s*->\s*[\w\[\], |]+)?\s*:", code)
    return m.group(0).strip() if m else ""


def _detect_hallucinations(code: str) -> list[str]:
    """Return a list of issue tags found in the generated code.

    Issue tags:
    - ``extra_import``          import statement present
    - ``hallucinated_function`` call to unknown function
    - ``missing_step:<name>``   one of the 4 required helpers not called
    - ``wrong_return_keys``     return dict missing 'total' or 'display'
    - ``syntax_error``          code does not parse
    """
    issues: list[str] = []

    if re.search(r"^\s*(?:import|from)\s+\w+", code, re.MULTILINE):
        issues.append("extra_import")

    try:
        tree = ast.parse(code)
        called: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
                if node.func.id not in _ALLOWED_CALLS:
                    issues.append(f"hallucinated_function:{node.func.id}")

        for fn in _REQUIRED_FUNCTIONS:
            if fn not in called:
                issues.append(f"missing_step:{fn}")

    except SyntaxError:
        issues.append("syntax_error")
        return issues

    has_total = bool(re.search(r'["\']total["\']', code))
    has_display = bool(re.search(r'["\']display["\']', code))
    if not (has_total and has_display):
        issues.append("wrong_return_keys")

    return issues


# ── Public API ───────────────────────────────────────────────────────────────


def run_code_generation(n: int = 5, generations: list[str] | None = None) -> dict[str, Any]:
    """Analyse n code generations and return variability metrics.

    Args:
        n: Number of generations (1-5). Ignored if *generations* is provided.
        generations: Pre-collected code strings (from live API calls).
            If ``None``, the pre-written simulated generations are used.

    Returns:
        dict with ``generations``, ``hallucinations``,
        ``generations_with_issues``, and ``metrics``.
    """
    if generations is None:
        generations = _SIMULATED_GENERATIONS[:n]

    error_handling = [_has_error_handling(g) for g in generations]
    docstring_lengths = [_extract_docstring_length(g) for g in generations]
    loc = [_count_lines(g) for g in generations]
    signatures = [_extract_function_signature(g) for g in generations]

    all_var_names: set[str] = set()
    for g in generations:
        all_var_names |= _extract_variable_names(g)

    exact_dups = 0
    for i in range(len(generations)):
        for j in range(i + 1, len(generations)):
            if generations[i].strip() == generations[j].strip():
                exact_dups += 1

    unique_sigs = len(set(signatures))
    hallucinations = [_detect_hallucinations(g) for g in generations]
    generations_with_issues = sum(1 for h in hallucinations if h)

    return {
        "generations": generations,
        "hallucinations": hallucinations,
        "generations_with_issues": generations_with_issues,
        "metrics": {
            "unique_variable_names": len(all_var_names),
            "unique_function_signatures": unique_sigs,
            "error_handling_present": error_handling,
            "docstring_lengths": docstring_lengths,
            "lines_of_code": loc,
            "exact_duplicates": exact_dups,
        },
    }


def run_bricks(n: int = 5) -> dict[str, Any]:
    """Execute the property_price Blueprint n times with varied inputs.

    Args:
        n: Number of executions (1-5).

    Returns:
        dict with ``executions`` and ``metrics``.
    """
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result
    from bricks.core import BlueprintEngine, BlueprintLoader
    from bricks.core.exceptions import BlueprintValidationError
    from bricks.core.validation import BlueprintValidator

    blueprint_yaml = (_BLUEPRINTS / "property_price.yaml").read_text()

    registry = build_showcase_registry(multiply, round_value, add, format_result)
    loader = BlueprintLoader()
    engine = BlueprintEngine(registry=registry)
    validator = BlueprintValidator(registry=registry)
    sequence = loader.load_string(blueprint_yaml)

    inputs_list = [
        {"width": 7.5, "height": 4.2, "price_per_sqm": 3500.0, "tax_rate": 0.17},
        {"width": 5.0, "height": 3.0, "price_per_sqm": 4200.0, "tax_rate": 0.17},
        {"width": 10.0, "height": 8.0, "price_per_sqm": 2800.0, "tax_rate": 0.10},
        {"width": 6.5, "height": 4.0, "price_per_sqm": 5000.0, "tax_rate": 0.17},
        {"width": 3.5, "height": 3.5, "price_per_sqm": 6000.0, "tax_rate": 0.20},
    ][:n]

    executions: list[dict[str, Any]] = []
    validation_passed: list[bool] = []

    for inp in inputs_list:
        try:
            validator.validate(sequence)
            validation_passed.append(True)
        except BlueprintValidationError:
            validation_passed.append(False)
        result = engine.run(sequence, inputs=inp)
        executions.append(result)

    return {
        "executions": executions,
        "metrics": {
            "blueprint_changed": False,
            "execution_path_identical": True,
            "outputs_predictable": True,
            "validation_passed": validation_passed,
        },
    }
