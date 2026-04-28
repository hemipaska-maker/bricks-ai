"""Tests for the ``bricks playground run`` headless scenario subcommand.

The CLI is the headless equivalent of one web playground run: load a
scenario (preset stem or YAML path), run BricksEngine on the bundled
data, optionally run RawLLMEngine alongside, and print three labeled
sections (input data, composed blueprint, outputs).

Tests stub the LiteLLM provider and the engines so each case runs in
milliseconds without touching a real model.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from bricks.cli.main import app

_runner = CliRunner()


def _stub_engine_result(outputs: dict[str, object], *, dsl_code: str = "@flow\ndef f(): pass\n") -> SimpleNamespace:
    """Mimic ``bricks.playground.engine.EngineResult`` shape used by ``run``."""
    return SimpleNamespace(
        outputs=outputs,
        dsl_code=dsl_code,
        raw_response="",
        error="",
    )


def test_run_help_exits_zero() -> None:
    """``bricks playground run --help`` lists the subcommand options."""
    r = _runner.invoke(app, ["playground", "run", "--help"])
    assert r.exit_code == 0


def test_run_resolves_preset_name_and_prints_three_sections() -> None:
    """A bare preset name resolves to the bundled YAML and the three
    labeled sections appear in the output."""
    with (
        patch("bricks.llm.litellm_provider.LiteLLMProvider"),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"active_count": 9, "total_active_revenue": 1524.0}),
        ),
    ):
        r = _runner.invoke(app, ["playground", "run", "crm_pipeline"])

    assert r.exit_code == 0, r.output
    assert "=== INPUT DATA" in r.output
    assert "=== COMPOSED BLUEPRINT (bricks) ===" in r.output
    assert "=== OUTPUTS (bricks) ===" in r.output
    # Compare-raw not requested; raw section must NOT appear.
    assert "OUTPUTS (raw_llm)" not in r.output
    # Output values surface in the printed dict.
    assert "active_count" in r.output


def test_run_resolves_yaml_path(tmp_path: Path) -> None:
    """A ``.yaml`` path is treated as a literal file (not a preset stem)."""
    custom = tmp_path / "my.yaml"
    custom.write_text(
        "name: custom\ndescription: tiny\ntask_text: count items\ndata:\n  - {id: 1}\n  - {id: 2}\nmodel: claudecode\n",
        encoding="utf-8",
    )

    with (
        patch("bricks.llm.litellm_provider.LiteLLMProvider"),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"count": 2}),
        ),
    ):
        r = _runner.invoke(app, ["playground", "run", str(custom)])

    assert r.exit_code == 0, r.output
    assert "INPUT DATA (custom)" in r.output
    assert "count" in r.output


def test_run_compare_raw_runs_raw_llm_engine_too() -> None:
    """``--compare-raw`` adds the raw_llm output block."""
    with (
        patch("bricks.llm.litellm_provider.LiteLLMProvider"),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"x": 1}),
        ),
        patch(
            "bricks.playground.engine.RawLLMEngine.solve",
            return_value=_stub_engine_result({"x": 1}, dsl_code=""),
        ),
    ):
        r = _runner.invoke(app, ["playground", "run", "crm_pipeline", "--compare-raw"])

    assert r.exit_code == 0, r.output
    assert "=== OUTPUTS (bricks) ===" in r.output
    assert "=== OUTPUTS (raw_llm) ===" in r.output


def test_run_unknown_preset_exits_1_with_helpful_message() -> None:
    """Bogus preset name surfaces the resolver's listing in stderr."""
    r = _runner.invoke(app, ["playground", "run", "no_such_preset_42"])
    assert r.exit_code == 1
    # The error mentions the unknown name AND lists bundled presets so the
    # user sees what's available without re-reading docs.
    assert "no_such_preset_42" in r.output
    assert "crm_pipeline" in r.output


def test_run_uses_inferred_provider_for_claudecode_preset() -> None:
    """All bundled presets declare ``model: claudecode`` — the CLI must
    infer ``claude_code`` (not LiteLLM) so the run actually works."""
    captured: dict[str, str] = {}

    def fake_build(*, provider: str, model: str, api_key: str) -> object:
        captured["provider"] = provider
        captured["model"] = model
        captured["api_key"] = api_key
        return SimpleNamespace()

    with (
        patch("bricks.playground.provider_factory.build_provider", new=fake_build),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"x": 1}),
        ),
    ):
        r = _runner.invoke(app, ["playground", "run", "crm_pipeline"])

    assert r.exit_code == 0, r.output
    assert captured["provider"] == "claude_code"
    # API key resolution skips claude_code (no key needed).
    assert captured["api_key"] == ""


def test_run_explicit_provider_flag_overrides_inference() -> None:
    """``--provider`` wins over the inference rules."""
    captured: dict[str, str] = {}

    def fake_build(*, provider: str, model: str, api_key: str) -> object:
        captured["provider"] = provider
        captured["model"] = model
        return SimpleNamespace()

    with (
        patch("bricks.playground.provider_factory.build_provider", new=fake_build),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"x": 1}),
        ),
    ):
        r = _runner.invoke(
            app,
            ["playground", "run", "crm_pipeline", "--provider", "anthropic", "--api-key", "k"],
        )

    assert r.exit_code == 0, r.output
    assert captured["provider"] == "anthropic"


def test_run_model_flag_overrides_scenario_model() -> None:
    """``--model`` lets the user swap the model without editing the YAML."""
    captured: dict[str, str] = {}

    def fake_build(*, provider: str, model: str, api_key: str) -> object:
        captured["model"] = model
        return SimpleNamespace()

    with (
        patch("bricks.playground.provider_factory.build_provider", new=fake_build),
        patch(
            "bricks.playground.engine.BricksEngine.solve",
            return_value=_stub_engine_result({"x": 1}),
        ),
    ):
        r = _runner.invoke(
            app,
            ["playground", "run", "crm_pipeline", "--model", "gpt-4o-mini", "--api-key", "k"],
        )

    assert r.exit_code == 0, r.output
    assert captured["model"] == "gpt-4o-mini"


def test_run_anthropic_without_key_exits_1() -> None:
    """BYOK rule: anthropic without an API key (flag or env) fails fast."""
    with patch.dict("os.environ", {"BRICKS_API_KEY": "", "ANTHROPIC_API_KEY": ""}, clear=False):
        # Make sure no umbrella key bleeds in from the host shell.
        import os

        os.environ.pop("BRICKS_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        r = _runner.invoke(app, ["playground", "run", "crm_pipeline", "--provider", "anthropic"])

    assert r.exit_code == 1
    assert "anthropic" in r.output
    assert "API_KEY" in r.output
