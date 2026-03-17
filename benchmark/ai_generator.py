"""AI generation for live mode: calls Anthropic API to generate YAML and Python."""

from __future__ import annotations

import os
from typing import Any

from bricks.core import BrickRegistry
from bricks.core.utils import blueprint_to_yaml, strip_code_fence


def generate_bricks_yaml(
    intent: str,
    registry: BrickRegistry,
    inputs: dict[str, Any] | None = None,
    expected_outputs: list[str] | None = None,
) -> tuple[str, int]:
    """Generate Bricks YAML via BlueprintComposer.

    Args:
        intent: Natural language description of what to compute.
        registry: The brick registry to use.
        inputs: Scenario inputs dict -- constrains the AI to use the same
            parameter names so the generated YAML is runnable with the
            scenario's test data.
        expected_outputs: Expected output key names -- constrains the AI to
            use the same keys in outputs_map for correct comparison.

    Returns:
        (yaml_string, total_tokens_used)
    """
    try:
        from bricks.ai import BlueprintComposer
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed. Run: pip install -e '.[ai]'") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set. Set it or use demo mode (no --live flag).")

    # Enrich the intent with exact input/output constraints so the AI
    # generates YAML that is compatible with the scenario's test data.
    enriched_intent = intent
    if inputs:
        input_names = ", ".join(inputs.keys())
        enriched_intent += f"\n\nYou MUST use exactly these input parameter names: {input_names}"
    if expected_outputs:
        output_names = ", ".join(expected_outputs)
        enriched_intent += f"\nYou MUST use exactly these keys in outputs_map: {output_names}"

    composer = BlueprintComposer(registry=registry, api_key=api_key)
    sequence, input_tokens, output_tokens = composer.compose_with_usage(enriched_intent)
    yaml_str = blueprint_to_yaml(sequence)
    return yaml_str, input_tokens + output_tokens


def generate_python_code(
    intent: str,
    available_functions: list[tuple[str, str]],
    inputs: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """Generate Python code via Anthropic API.

    Args:
        intent: Natural language description of what to compute.
        available_functions: List of (function_name, docstring) tuples.
        inputs: Scenario inputs dict -- tells the AI what variables are
            available so it uses inputs['key'] correctly.

    Returns:
        (python_code, total_tokens_used)

    Token count includes both input and output tokens from the API response.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed. Run: pip install -e '.[ai]'") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set. Set it or use demo mode (no --live flag).")

    client = anthropic.Anthropic(api_key=api_key)

    func_descriptions = "\n".join(f"- {name}: {doc}" for name, doc in available_functions)

    inputs_hint = ""
    if inputs:
        inputs_hint = "\n\nAvailable inputs (access via inputs['key']):\n" + "\n".join(
            f"- inputs['{k}'] = {v!r}" for k, v in inputs.items()
        )

    system_prompt = (
        "You are an expert Python programmer. "
        "Generate Python code that solves the given task.\n\n"
        "Available functions:\n"
        f"{func_descriptions}\n\n"
        "Requirements:\n"
        "- Use only the available functions listed above\n"
        "- Do NOT import any modules or define new functions\n"
        "- Store the final result in a variable named 'result' as a dict\n"
        "- The code must be runnable with exec()\n"
        "- Access input values via inputs['key'] (a dict is pre-defined)\n"
        "- Output ONLY raw Python code -- no markdown, no code fences"
    )

    user_prompt = f"Task: {intent}{inputs_hint}\n\nGenerate Python code that solves this task."

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    code = response.content[0].text
    code = strip_code_fence(code)
    total_tokens = response.usage.input_tokens + response.usage.output_tokens
    return code, total_tokens
