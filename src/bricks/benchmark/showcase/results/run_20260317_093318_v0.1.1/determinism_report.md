# Bricks v0.1.1 -- Scenario D: Determinism Benchmark

> **Claim:** Code generation produces a different program every time.
> Bricks Blueprints produce identical execution every time.

## Diff: Generation 1 vs Generation 3

Same prompt. Same model. Different output.

```diff
--- generation_1.py
+++ generation_3.py
@@ -1,34 +1,36 @@
 def calculate_property_price(width: float, height: float,
-                             price_per_sqm: float, tax_rate: float) -> dict:
+                            price_per_sqm: float, tax_rate: float) -> dict:
     """
-    Calculate property price including tax based on dimensions and rates.
+    Calculate the total property price including tax.

     Args:
-        width: Property width in meters (must be positive).
-        height: Property height in meters (must be positive).
-        price_per_sqm: Price per square meter (must be non-negative).
-        tax_rate: Tax rate as decimal (e.g., 0.19 for 19%).
+        width: Property width in meters (must be positive)
+        height: Property height in meters (must be positive)
+        price_per_sqm: Price per square meter in EUR (must be non-negative)
+        tax_rate: Tax rate as decimal (e.g., 0.19 for 19%)

     Returns:
-        dict: Contains 'total' (float) and 'display' (str) keys.
-              'total': Final price including tax.
-              'display': Formatted display string.
+        Dictionary with keys:
+            - 'total': float, total price including tax
+            - 'display': str, formatted display string

     Raises:
-        ValueError: If width or height is not positive.
+        ValueError: If width or height is not positive, or price_per_sqm is negative
     """
-    # Validate dimensions
+    # Input validation
     if width <= 0:
-        raise ValueError(f"Width must be positive, got {width}")
+        raise ValueError(f"width must be positive, got {width}")
     if height <= 0:
-        raise ValueError(f"Height must be positive, got {height}")
+        raise ValueError(f"height must be positive, got {height}")
+    if price_per_sqm < 0:
+        raise ValueError(f"price_per_sqm must be non-negative, got {price_per_sqm}")

     # Step 1: Compute area = width * height, rounded to 2dp
     area_result = multiply(width, height)
     area = area_result['result']

-    rounded_area_result = round_value(area, decimals=2)
-    area = rounded_area_result['result']
+    area_rounded = round_value(area, decimals=2)
+    area = area_rounded['result']

     # Step 2: Compute base_price = area * price_per_sqm
     base_price_result = multiply(area, price_per_sqm)
```

## Metrics

| Metric | Code Generation (5 runs) | Bricks Blueprint (5 runs) |
|--------|--------------------------|---------------------------|
| Unique variable names | 19 distinct names across runs | N/A — no variables, just YAML wiring |
| Unique function signatures | 3 distinct signature(s) | N/A — Blueprint schema is fixed |
| Error handling consistent | Y, Y, Y, Y, Y | Always — Brick has it built-in |
| Docstring length (chars) | 603, 689, 590, 557, 582 | N/A — Brick has fixed description |
| Lines of code | 42, 38, 44, 44, 48 | Blueprint is always the same 47 lines |
| Exact duplicate outputs | 0 pair(s) identical | All 5 executions identical (same YAML) |
| Pre-execution validation | None — code runs and you hope | Y, Y, Y, Y, Y — dry-run before every run |

## The Blueprint (6 steps)

This is the same file used in all 5 executions. It will never change.

```yaml
name: property_price
description: "Calculate property price: area, base price, tax, total, format"
inputs:
  width: "float"
  height: "float"
  price_per_sqm: "float"
  tax_rate: "float"
steps:
  - name: calculate_area
    brick: multiply
    params:
      a: "${inputs.width}"
      b: "${inputs.height}"
    save_as: area
  - name: round_area
    brick: round_value
    params:
      value: "${area.result}"
      decimals: 2
    save_as: rounded_area
  - name: calculate_base_price
    brick: multiply
    params:
      a: "${rounded_area.result}"
      b: "${inputs.price_per_sqm}"
    save_as: base_price
  - name: calculate_tax
    brick: multiply
    params:
      a: "${base_price.result}"
      b: "${inputs.tax_rate}"
    save_as: tax_amount
  - name: calculate_total
    brick: add
    params:
      a: "${base_price.result}"
      b: "${tax_amount.result}"
    save_as: total
  - name: format_display
    brick: format_result
    params:
      label: "Total (EUR)"
      value: "${total.result}"
    save_as: formatted
outputs_map:
  total: "${total.result}"
  display: "${formatted.display}"
```

## Conclusion

Code generation produces a different program every time. Across 5 runs with the identical prompt, the model used 19 distinct variable names, sometimes varied its error handling, and produced functions ranging from 38 to 48 lines. Some are better, some are worse — you cannot predict which. Bricks produces the same execution every time: the Blueprint is validated once, stored as a YAML file, and executed identically on every subsequent run. You validate once, trust forever.

## Hallucination Detection

In this run, **0/5** generation(s) had at least one issue.

- **Generation 1:** clean
- **Generation 2:** clean
- **Generation 3:** clean
- **Generation 4:** clean
- **Generation 5:** clean

_Note: This rate varies — repeated benchmarks may show different results, which itself proves the non-determinism._
