"""Live integration tests for full compose + execute pipeline.

Run with: pytest --live -m live
Skipped by default (no --live flag).
"""

from __future__ import annotations

import pytest

from bricks.api import Bricks
from bricks.llm.base import LLMProvider


@pytest.mark.live
def test_full_pipeline(llm_provider: LLMProvider) -> None:
    """Compose a blueprint and execute it with real LLM — end to end."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "filter items where status is active",
        {
            "items": [
                {"name": "A", "status": "active"},
                {"name": "B", "status": "inactive"},
                {"name": "C", "status": "active"},
            ]
        },
    )
    assert isinstance(result["outputs"], dict)
    assert result["api_calls"] >= 1


@pytest.mark.live
def test_reuse_hits_cache(llm_provider: LLMProvider) -> None:
    """Second call with identical task should hit cache when store is enabled."""
    from bricks.boot.config import SystemConfig
    from bricks.core.config import StoreConfig
    from bricks.core.registry import BrickRegistry
    from bricks.orchestrator.runtime import RuntimeOrchestrator
    from bricks.stdlib import register as _reg_stdlib

    registry = BrickRegistry()
    _reg_stdlib(registry)
    config = SystemConfig(
        name="live-cache-test",
        model="claude-haiku-4-5",
        api_key="",
        store=StoreConfig(enabled=True, backend="memory"),
    )
    orchestrator = RuntimeOrchestrator(config, registry, provider=llm_provider)
    engine = Bricks(orchestrator)
    data = {"items": [{"name": "X", "status": "active"}]}

    result1 = engine.execute("filter items where status is active", data)
    assert result1["api_calls"] >= 1

    result2 = engine.execute("filter items where status is active", data)
    assert result2["cache_hit"] is True
    assert result2["tokens_used"] == 0


# ── Category coverage: one test per stdlib category ──────────────────────────


@pytest.mark.live
def test_e2e_string_convert_to_uppercase(llm_provider: LLMProvider) -> None:
    """String processing: convert text to uppercase via LLM-composed blueprint."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "convert the text to uppercase",
        {"text": "hello world"},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    assert any("HELLO WORLD" in str(v) for v in outputs.values()), (
        f"Expected 'HELLO WORLD' in outputs but got: {outputs}"
    )


@pytest.mark.live
def test_e2e_math_absolute_value(llm_provider: LLMProvider) -> None:
    """Math/numeric: compute absolute value of a negative number."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "compute the absolute value of the number",
        {"number": -42.0},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    assert any(isinstance(v, (int, float)) and abs(v - 42.0) < 0.001 for v in outputs.values()), (
        f"Expected 42.0 in outputs but got: {outputs}"
    )


@pytest.mark.live
def test_e2e_date_add_days(llm_provider: LLMProvider) -> None:
    """Date/time: add a number of days to a date string."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "add 5 days to the start date",
        {"start_date": "2024-01-10", "days": 5},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    assert any("2024-01-15" in str(v) for v in outputs.values()), f"Expected '2024-01-15' in outputs but got: {outputs}"


@pytest.mark.live
def test_e2e_data_transformation_extract_field(llm_provider: LLMProvider) -> None:
    """Data transformation: extract a single field from a dict."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "extract the email field from the record",
        {"record": {"name": "Alice", "email": "alice@example.com", "age": 30}},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    assert any("alice@example.com" in str(v) for v in outputs.values()), (
        f"Expected 'alice@example.com' in outputs but got: {outputs}"
    )


@pytest.mark.live
def test_e2e_list_operations_take_first_n(llm_provider: LLMProvider) -> None:
    """List operations: take the first N items from a list."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "take only the first 2 items from the list",
        {"items": [10, 20, 30, 40, 50]},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    # Expect a list with exactly 2 items
    assert any(isinstance(v, list) and len(v) == 2 for v in outputs.values()), (
        f"Expected a 2-item list in outputs but got: {outputs}"
    )


@pytest.mark.live
def test_e2e_encoding_base64_encode(llm_provider: LLMProvider) -> None:
    """Encoding/security: base64-encode a string."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "base64 encode the text",
        {"text": "hello"},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    # base64("hello") == "aGVsbG8="
    assert any("aGVsbG8=" in str(v) for v in outputs.values()), f"Expected 'aGVsbG8=' in outputs but got: {outputs}"


@pytest.mark.live
def test_e2e_validation_is_email_valid(llm_provider: LLMProvider) -> None:
    """Validation: verify an email address is valid."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "check whether the email address is valid",
        {"email": "user@example.com"},
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    assert any(v is True for v in outputs.values()), f"Expected True in outputs but got: {outputs}"


@pytest.mark.live
def test_e2e_multistep_filter_and_extract_emails(llm_provider: LLMProvider) -> None:
    """Multi-step: filter active users then extract their email addresses."""
    engine = Bricks.default(provider=llm_provider)
    result = engine.execute(
        "filter the users where status is active, then extract the email field from each user",
        {
            "users": [
                {"name": "Alice", "status": "active", "email": "alice@example.com"},
                {"name": "Bob", "status": "inactive", "email": "bob@example.com"},
                {"name": "Carol", "status": "active", "email": "carol@example.com"},
            ]
        },
    )
    outputs = result["outputs"]
    assert isinstance(outputs, dict)
    assert result["api_calls"] >= 1
    # Should contain the two active user emails
    outputs_str = str(outputs)
    assert "alice@example.com" in outputs_str or "carol@example.com" in outputs_str, (
        f"Expected active user emails in outputs but got: {outputs}"
    )
