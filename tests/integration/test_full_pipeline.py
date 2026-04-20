"""Integration tests: full pipeline from YAML to executed results."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import cast

import pytest

from bricks.core.brick import BrickFunction, brick
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import BlueprintValidationError, BrickExecutionError
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import BlueprintValidator


def _make_math_registry() -> BrickRegistry:
    reg = BrickRegistry()

    @brick(tags=["math"], description="Add two numbers")
    def add(a: float, b: float) -> float:
        return a + b

    @brick(tags=["math"], description="Multiply two numbers")
    def multiply(a: float, b: float) -> float:
        return a * b

    @brick(tags=["math"], description="Round a float")
    def round_val(value: float, decimals: int = 2) -> float:
        return round(value, decimals)

    @brick(tags=["io"])
    def to_string(value: float) -> str:
        return str(value)

    reg.register("add", cast(BrickFunction, add), cast(BrickFunction, add).__brick_meta__)
    reg.register("multiply", cast(BrickFunction, multiply), cast(BrickFunction, multiply).__brick_meta__)
    reg.register("round_val", cast(BrickFunction, round_val), cast(BrickFunction, round_val).__brick_meta__)
    reg.register("to_string", cast(BrickFunction, to_string), cast(BrickFunction, to_string).__brick_meta__)
    return reg


class TestSingleStepPipeline:
    def test_single_step_add(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: simple_add
inputs:
  x: "float"
  y: "float"
steps:
  - name: add_step
    brick: add
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: total
outputs_map:
  result: "${total}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 3.0, "y": 4.0}).outputs
        assert out["result"] == 7.0, f"Expected 7.0, got {out['result']!r}"

    def test_literal_params(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: literal_add
steps:
  - name: step
    brick: add
    params:
      a: 10.0
      b: 5.0
    save_as: total
outputs_map:
  result: "${total}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["result"] == 15.0, f"Expected 15.0, got {out['result']!r}"

    def test_string_output(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: to_str
steps:
  - name: s1
    brick: to_string
    params:
      value: 42.0
    save_as: text
outputs_map:
  label: "${text}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["label"] == "42.0", f"Expected '42.0', got {out['label']!r}"

    def test_no_outputs_map(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: no_outputs
steps:
  - name: step
    brick: add
    params:
      a: 1.0
      b: 2.0
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out == {}, f"Expected {{}}, got {out!r}"


class TestMultiStepPipeline:
    def test_chained_steps(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: chain
inputs:
  a: "float"
  b: "float"
  c: "float"
steps:
  - name: first_add
    brick: add
    params:
      a: "${inputs.a}"
      b: "${inputs.b}"
    save_as: ab_sum
  - name: second_add
    brick: add
    params:
      a: "${ab_sum}"
      b: "${inputs.c}"
    save_as: final_sum
outputs_map:
  total: "${final_sum}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"a": 1.0, "b": 2.0, "c": 3.0}).outputs
        assert out["total"] == 6.0, f"Expected 6.0, got {out['total']!r}"

    def test_multiply_then_round(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: mul_round
inputs:
  x: "float"
  y: "float"
steps:
  - name: mul
    brick: multiply
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: product
  - name: rnd
    brick: round_val
    params:
      value: "${product}"
      decimals: 2
    save_as: rounded
outputs_map:
  result: "${rounded}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 7.5, "y": 4.2}).outputs
        assert out["result"] == 31.5, f"Expected 31.5, got {out['result']!r}"

    def test_three_steps_chained(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: triple_chain
steps:
  - name: s1
    brick: add
    params:
      a: 2.0
      b: 3.0
    save_as: r1
  - name: s2
    brick: multiply
    params:
      a: "${r1}"
      b: 4.0
    save_as: r2
  - name: s3
    brick: round_val
    params:
      value: "${r2}"
      decimals: 1
    save_as: r3
outputs_map:
  result: "${r3}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["result"] == 20.0, f"Expected 20.0, got {out['result']!r}"  # (2+3)*4 = 20

    def test_add_then_stringify(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: add_then_str
steps:
  - name: sum_step
    brick: add
    params:
      a: 8.0
      b: 2.0
    save_as: sum_result
  - name: str_step
    brick: to_string
    params:
      value: "${sum_result}"
    save_as: text_result
outputs_map:
  label: "${text_result}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["label"] == "10.0", f"Expected '10.0', got {out['label']!r}"


class TestValidationIntegration:
    def test_validate_then_run(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: validated_seq
inputs:
  n: "float"
steps:
  - name: double
    brick: multiply
    params:
      a: "${inputs.n}"
      b: 2.0
    save_as: doubled
outputs_map:
  result: "${doubled}"
""")
        validator = BlueprintValidator(registry=reg)
        validator.validate(seq)  # raises on failure

        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"n": 5.0}).outputs
        assert out["result"] == 10.0, f"Expected 10.0, got {out['result']!r}"

    @pytest.mark.parametrize(
        "brick_name",
        ["nonexistent_brick", "unknown_op"],
    )
    def test_validation_catches_missing_brick(self, brick_name: str) -> None:
        """Validation raises for any unregistered brick name."""
        reg = BrickRegistry()
        loader = BlueprintLoader()
        seq = loader.load_string(f"""
name: bad_seq
steps:
  - name: s1
    brick: {brick_name}
""")
        validator = BlueprintValidator(registry=reg)
        with pytest.raises(BlueprintValidationError) as exc_info:
            validator.validate(seq)
        assert any(brick_name in e for e in exc_info.value.errors), (
            f"Expected {brick_name!r} in errors: {exc_info.value.errors!r}"
        )

    def test_execution_error_propagates(self) -> None:
        reg = BrickRegistry()

        @brick()
        def always_fails(x: int) -> int:
            raise RuntimeError("intentional failure")

        reg.register(
            "always_fails",
            cast(BrickFunction, always_fails),
            cast(BrickFunction, always_fails).__brick_meta__,
        )
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: failing_seq
steps:
  - name: bad_step
    brick: always_fails
    params:
      x: 1
""")
        engine = BlueprintEngine(registry=reg)
        with pytest.raises(BrickExecutionError) as exc_info:
            engine.run(seq)
        assert "always_fails" in str(exc_info.value), f"Expected 'always_fails' in {str(exc_info.value)!r}"


class TestDiscoveryIntegration:
    def test_discover_and_run(self, tmp_path: Path) -> None:
        brick_file = tmp_path / "math_ops.py"
        brick_file.write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Square a number")
                def square(x: float) -> float:
                    return x * x
            """).strip()
        )

        from bricks.core.discovery import BrickDiscovery

        reg = BrickRegistry()
        disc = BrickDiscovery(registry=reg)
        disc.discover_path(brick_file)
        assert reg.has("square"), "Expected 'square' to be registered"

        loader = BlueprintLoader()
        seq = loader.load_string("""
name: square_seq
inputs:
  n: "float"
steps:
  - name: sq
    brick: square
    params:
      x: "${inputs.n}"
    save_as: squared
outputs_map:
  result: "${squared}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"n": 4.0}).outputs
        assert out["result"] == 16.0, f"Expected 16.0, got {out['result']!r}"

    def test_discover_package_and_run(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "ops"
        pkg_dir.mkdir()
        (pkg_dir / "adder.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(description="Add one to a number")
                def add_one(n: float) -> float:
                    return n + 1.0
            """).strip()
        )

        from bricks.core.discovery import BrickDiscovery

        reg = BrickRegistry()
        disc = BrickDiscovery(registry=reg)
        disc.discover_package(pkg_dir)
        assert reg.has("add_one"), "Expected 'add_one' to be registered"

        loader = BlueprintLoader()
        seq = loader.load_string("""
name: add_one_seq
steps:
  - name: step
    brick: add_one
    params:
      n: 9.0
    save_as: result
outputs_map:
  out: "${result}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["out"] == 10.0, f"Expected 10.0, got {out['out']!r}"


class TestOutputsMap:
    def test_multiple_outputs(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: multi_out
inputs:
  x: "float"
  y: "float"
steps:
  - name: s1
    brick: add
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: sum_val
  - name: s2
    brick: multiply
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: prod_val
outputs_map:
  sum: "${sum_val}"
  product: "${prod_val}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 3.0, "y": 4.0}).outputs
        assert out["sum"] == 7.0, f"Expected 7.0, got {out['sum']!r}"
        assert out["product"] == 12.0, f"Expected 12.0, got {out['product']!r}"

    def test_literal_output_value(self) -> None:
        """Outputs map with a literal value (no reference) passthrough."""
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: literal_out
steps:
  - name: s1
    brick: add
    params:
      a: 5.0
      b: 5.0
    save_as: total
outputs_map:
  result: "${total}"
  label: "computed"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["result"] == 10.0, f"Expected 10.0, got {out['result']!r}"
        assert out["label"] == "computed", f"Expected 'computed', got {out['label']!r}"


class TestLoaderIntegration:
    def test_load_string_and_run(self) -> None:
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_string("""
name: round_test
steps:
  - name: r1
    brick: round_val
    params:
      value: 3.14159
      decimals: 2
    save_as: rounded
outputs_map:
  pi_approx: "${rounded}"
""")
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["pi_approx"] == 3.14, f"Expected 3.14, got {out['pi_approx']!r}"

    def test_load_file_and_run(self, tmp_path: Path) -> None:
        seq_file = tmp_path / "test_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: file_load_test
                steps:
                  - name: step1
                    brick: add
                    params:
                      a: 100.0
                      b: 50.0
                    save_as: total
                outputs_map:
                  result: "${total}"
            """).strip()
        )
        reg = _make_math_registry()
        loader = BlueprintLoader()
        seq = loader.load_file(seq_file)
        engine = BlueprintEngine(registry=reg)
        out = engine.run(seq).outputs
        assert out["result"] == 150.0, f"Expected 150.0, got {out['result']!r}"
