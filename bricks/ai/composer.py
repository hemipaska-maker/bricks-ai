"""AI sequence composer: generates YAML sequences from natural language."""

from __future__ import annotations

import json
import re
from typing import Any

from bricks.core.exceptions import BrickError
from bricks.core.loader import SequenceLoader
from bricks.core.models import SequenceDefinition
from bricks.core.registry import BrickRegistry
from bricks.core.schema import registry_schema


class ComposerError(BrickError):
    """Raised when AI composition fails."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """Initialise the error.

        Args:
            message: Human-readable error description.
            cause: The underlying exception, if any.
        """
        super().__init__(message)
        self.cause = cause


# System prompt template for the AI model
_SYSTEM_PROMPT = """\
You are an expert at composing YAML sequences for the Bricks framework.

Given a natural language intent and a list of available bricks, you generate
a valid YAML sequence.

YAML sequence format:
```yaml
name: sequence_name        # snake_case name
description: "What it does"
inputs:
  param_name: "type"       # e.g. "int", "float", "str", "bool"
steps:
  - name: step_name        # snake_case step name
    brick: brick_name      # must be one of the available bricks
    params:
      key: "${inputs.param}"  # ${inputs.X} for inputs, ${save_as} for results
      key2: literal_value
    save_as: result_name   # snake_case; optional unless referenced later
outputs_map:
  output_key: "${result_name}"  # or "${inputs.X}" for pass-through
```

Rules:
- Only use bricks from the provided list
- step names and save_as names must be unique snake_case identifiers
- ${inputs.X} references require X to be declared in inputs
- ${name} references require name to be a save_as from a PRIOR step
- outputs_map values must reference declared inputs or prior save_as names
- Always output ONLY the YAML block, no explanation, wrapped in ```yaml ... ```
"""

_USER_PROMPT_TEMPLATE = """Available bricks:
{bricks_json}

Intent: {intent}

Generate the YAML sequence:"""


class SequenceComposer:
    """Generates SequenceDefinitions from natural language intent using Claude.

    Uses the Anthropic Messages API to translate natural language descriptions
    into valid YAML sequences, then parses and validates them.

    Requires the ``anthropic`` package: ``pip install bricks[ai]``
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    DEFAULT_MAX_TOKENS = 4096

    _client: Any

    def __init__(
        self,
        registry: BrickRegistry,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """Initialise the composer.

        Args:
            registry: The brick registry to describe to the AI.
            api_key: Anthropic API key.
            model: The Claude model to use.
            max_tokens: Maximum tokens for the response.

        Raises:
            ImportError: If the ``anthropic`` package is not installed.
        """
        try:
            import anthropic  # type: ignore[import-not-found]  # noqa: PLC0415

            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AI composition. "
                "Install with: pip install bricks[ai]"
            ) from exc

        self._registry = registry
        self._model = model
        self._max_tokens = max_tokens
        self._loader = SequenceLoader()

    def compose(self, intent: str) -> SequenceDefinition:
        """Compose a sequence from a natural language description.

        Sends the intent and registry schema to the AI model, parses the
        returned YAML, and returns a validated SequenceDefinition.

        Args:
            intent: Natural language description of the desired sequence.

        Returns:
            A validated SequenceDefinition.

        Raises:
            ComposerError: If the AI returns invalid YAML or the sequence
                fails Pydantic validation.
        """
        sequence, _, _ = self.compose_with_usage(intent)
        return sequence

    def compose_with_usage(self, intent: str) -> tuple[SequenceDefinition, int, int]:
        """Compose a sequence and return real token usage from the API.

        Same as ``compose()`` but also returns the exact token counts reported
        by the Anthropic API response, enabling accurate benchmarking of token
        efficiency compared to raw Python code generation.

        Args:
            intent: Natural language description of the desired sequence.

        Returns:
            A 3-tuple of ``(sequence, input_tokens, output_tokens)`` where
            ``input_tokens`` and ``output_tokens`` are the actual values from
            ``response.usage`` as reported by the Anthropic API.

        Raises:
            ComposerError: If the AI returns invalid YAML or the sequence
                fails Pydantic validation.
        """
        bricks_info = self._build_bricks_context()
        prompt = _USER_PROMPT_TEMPLATE.format(
            bricks_json=json.dumps(bricks_info, indent=2),
            intent=intent,
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ComposerError(f"API call failed: {exc}", cause=exc) from exc

        input_tokens: int = response.usage.input_tokens
        output_tokens: int = response.usage.output_tokens

        raw_text = self._extract_text(response)
        yaml_content = self._extract_yaml(raw_text)

        try:
            sequence = self._loader.load_string(yaml_content)
        except Exception as exc:
            raise ComposerError(
                f"AI-generated YAML is invalid: {exc}\n\nYAML:\n{yaml_content}",
                cause=exc,
            ) from exc

        return sequence, input_tokens, output_tokens

    def _build_bricks_context(self) -> list[dict[str, Any]]:
        """Build a JSON-serialisable list of brick descriptions.

        Returns:
            A list of dicts with name, description, tags, and parameters.
        """
        schemas = registry_schema(self._registry)
        # Simplify for the prompt: drop extra detail to save tokens
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "tags": s["tags"],
                "parameters": s["parameters"],
            }
            for s in schemas
        ]

    def _extract_text(self, response: Any) -> str:
        """Extract text content from an Anthropic response.

        Args:
            response: The raw Anthropic API response object.

        Returns:
            The text content of the first text block.

        Raises:
            ComposerError: If no text block is found.
        """
        for block in response.content:
            if hasattr(block, "text"):
                return str(block.text)
        raise ComposerError("AI response contained no text block")

    def _extract_yaml(self, text: str) -> str:
        """Extract YAML content from a markdown code block.

        Looks for ```yaml ... ``` or ``` ... ``` blocks. Falls back to the
        raw text if no code block is found.

        Args:
            text: Raw text from the AI response.

        Returns:
            The YAML string to parse.
        """
        # Match ```yaml ... ``` or ``` ... ```
        pattern = re.compile(r"```(?:yaml)?\s*\n(.*?)```", re.DOTALL)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        # Fall back to the entire text (the model may not have used a code block)
        return text.strip()
