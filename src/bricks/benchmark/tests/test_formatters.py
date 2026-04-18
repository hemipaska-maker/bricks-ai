"""Tests for the benchmark formatters module."""

from __future__ import annotations

from bricks.benchmark.showcase.formatters import count_yaml_steps, estimate_cost


class TestEstimateCost:
    """Tests for the estimate_cost function."""

    def test_zero(self) -> None:
        """Zero tokens = zero cost."""
        assert estimate_cost(0, 0) == 0.0

    def test_haiku_pricing(self) -> None:
        """1M input + 1M output at Haiku pricing = $4.80."""
        cost = estimate_cost(1_000_000, 1_000_000)
        assert abs(cost - 4.80) < 0.01

    def test_input_only(self) -> None:
        """Input-only cost at $0.80/M."""
        cost = estimate_cost(1_000_000, 0)
        assert abs(cost - 0.80) < 0.01


class TestCountYamlSteps:
    """Tests for the count_yaml_steps function."""

    def test_counts_steps(self) -> None:
        """Counts '- name:' entries."""
        yaml = "steps:\n  - name: step1\n  - name: step2\n  - name: step3"
        assert count_yaml_steps(yaml) == 3

    def test_empty(self) -> None:
        """Empty string has 0 steps."""
        assert count_yaml_steps("") == 0
