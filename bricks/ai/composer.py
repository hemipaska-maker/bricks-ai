"""AI blueprint composer: single-call YAML generation from natural language.

No tool_use, no multi-turn conversation. The LLM outputs Blueprint YAML as
plain text, which we validate and execute locally.
"""

from __future__ import annotations

import inspect as _inspect
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from bricks.core.exceptions import BlueprintValidationError, BrickError, DuplicateBlueprintError
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.schema import compact_brick_signatures, output_key_table, output_keys, parse_description_keys
from bricks.core.selector import AllBricksSelector, BrickSelector
from bricks.core.utils import strip_code_fence
from bricks.core.validation import BlueprintValidator

if TYPE_CHECKING:
    from bricks.store.blueprint_store import BlueprintStore


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


class CallDetail(BaseModel):
    """Detail for a single API call within a compose attempt."""

    call_number: int
    system_prompt: str = ""
    user_prompt: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    yaml_text: str = ""
    is_valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)


class ComposeResult(BaseModel):
    """Result of a Blueprint composition attempt."""

    task: str
    blueprint_yaml: str = ""
    is_valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    calls: list[CallDetail] = Field(default_factory=list)
    api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    duration_seconds: float = 0.0
    system_prompt: str = ""
    cache_hit: bool = False


# System prompt — under 300 tokens without signatures/output_keys/example.
_COMPOSE_SYSTEM = """\
You are a Blueprint composer. Given a task and available bricks, output ONLY \
a valid Blueprint YAML block. No explanation, no markdown fences, just raw YAML.

Available bricks:
{signatures}

{output_keys}

Blueprint format:
name: blueprint_name
inputs:
  param_name: value
steps:
  - name: step_name
    brick: brick_name
    params:
      key: "${{inputs.param_name}}"
      key2: "${{prior_step.field}}"
      key3: 42.0
    save_as: result_name
outputs_map:
  output_key: "${{result_name.field}}"

Reference syntax:
- ${{inputs.X}} for task inputs declared in the inputs section
- ${{save_as_name.field}} for prior step outputs
- Literal values (numbers, strings) allowed

Rules:
- Only use brick names from the list above.
- Declare all task parameters in the inputs section. Use ${{inputs.X}} to reference them in steps.
- Every step referenced later needs save_as.
- Step names must be unique snake_case.
- outputs_map values must use ${{inputs.X}} or ${{save_as.field}} syntax.
- Output keys are listed above. Use EXACTLY those keys in ${{step.key}} references.
- Use a descriptive, unique blueprint name (the name: field).

{example}\
"""

_RETRY_PROMPT = """\
Original task:
{task}

The following Blueprint YAML has validation errors:

{yaml}

Errors:
{errors}

Output ONLY the corrected YAML. Nothing else.\
"""


def _build_example(registry: BrickRegistry) -> str:
    """Auto-generate a 2-step worked example from the first two bricks in the registry.

    Shows exact ``${save_as.output_key}`` syntax so the LLM sees a concrete
    reference chain. Uses literal params for step 1, a cross-step reference
    for step 2.

    Args:
        registry: Registry of available bricks (sorted alphabetically).

    Returns:
        A YAML example block prefixed with ``Example (2-step chain):``.
    """
    bricks = sorted(registry.list_all(), key=lambda x: x[0])
    if len(bricks) < 2:
        return ""

    name1, meta1 = bricks[0]
    name2, meta2 = bricks[1]
    callable1, _ = registry.get(name1)
    callable2, _ = registry.get(name2)

    keys1 = output_keys(callable1) or parse_description_keys(meta1.description)
    keys2 = output_keys(callable2) or parse_description_keys(meta2.description)
    out_key1 = keys1[0] if keys1 else "result"
    out_key2 = keys2[0] if keys2 else "result"

    # Build input declarations and param references for step 1
    input_decls, input_refs = _build_input_params(callable1)
    params2 = _build_ref_params(callable2, "step1", out_key1)

    lines = [
        "Example (2-step chain):",
        "name: example",
        "inputs:",
        *[f"  {line}" for line in input_decls],
        "steps:",
        "  - name: step1",
        f"    brick: {name1}",
        "    params:",
        *[f"      {line}" for line in input_refs],
        "    save_as: step1",
        "  - name: step2",
        f"    brick: {name2}",
        "    params:",
        *[f"      {line}" for line in params2],
        "    save_as: step2",
        "outputs_map:",
        f'  output: "${{step2.{out_key2}}}"',
    ]
    return "\n".join(lines)


def _build_input_params(callable_: Any) -> tuple[list[str], list[str]]:
    """Build input declarations and ``${inputs.X}`` references for a worked example.

    Args:
        callable_: A brick callable.

    Returns:
        Tuple of (input_declarations, param_references). Declarations go in the
        ``inputs:`` section, references go in step ``params:``.
    """
    try:
        sig = _inspect.signature(callable_)
        decls: list[str] = []
        refs: list[str] = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "inputs", "metadata"):
                continue
            ann = param.annotation
            if ann is float or ann is int:
                decls.append(f"{pname}: 1.0")
            else:
                decls.append(f'{pname}: "example"')
            refs.append(f'{pname}: "${{inputs.{pname}}}"')
        return decls, refs
    except (ValueError, TypeError):
        return ["x: 1.0"], ['x: "${inputs.x}"']


def _build_ref_params(callable_: Any, ref_step: str, ref_key: str) -> list[str]:
    """Build param lines with a cross-step reference for a worked example.

    Args:
        callable_: A brick callable.
        ref_step: The save_as name to reference.
        ref_key: The output key to reference.

    Returns:
        List of ``key: value`` strings, first numeric param uses a reference.
    """
    try:
        sig = _inspect.signature(callable_)
        lines: list[str] = []
        used_ref = False
        for pname, param in sig.parameters.items():
            if pname in ("self", "inputs", "metadata"):
                continue
            ann = param.annotation
            if (ann is float or ann is int) and not used_ref:
                lines.append(f'{pname}: "${{{ref_step}.{ref_key}}}"')
                used_ref = True
            elif ann is float or ann is int:
                lines.append(f"{pname}: 1.0")
            else:
                lines.append(f'{pname}: "example"')
        return lines
    except (ValueError, TypeError):
        return [f'{ref_step}: "${{{ref_step}.{ref_key}}}"']


_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2048
_MAX_API_CALLS = 2


def _extract_blueprint_name(yaml_text: str) -> str:
    """Extract the ``name:`` value from Blueprint YAML text.

    Scans for the first ``name:`` line without loading the full YAML document,
    so it works even on partially-valid YAML.

    Args:
        yaml_text: Raw YAML string from the LLM.

    Returns:
        The blueprint name, or ``"unknown"`` if not found.
    """
    for line in yaml_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip().strip('"').strip("'") or "unknown"
    return "unknown"


class BlueprintComposer:
    """Composes Blueprint YAML from a natural language task using a single LLM call.

    No tool_use, no multi-turn conversation. The LLM outputs YAML as text,
    which we validate and execute locally.

    If the first attempt fails validation, makes ONE retry with a fresh
    prompt containing the errors. Max 2 API calls total.

    Args:
        api_key: Anthropic API key.
        model: Model ID (default: claude-haiku-4-5-20251001).
        selector: BrickSelector for Stage 1 filtering (default: AllBricksSelector).
    """

    _client: Any

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        selector: BrickSelector | None = None,
        store: BlueprintStore | None = None,
    ) -> None:
        """Initialise the composer.

        Args:
            api_key: Anthropic API key.
            model: The Claude model to use.
            selector: BrickSelector for Stage 1 filtering. Defaults to AllBricksSelector.
            store: Optional blueprint store for caching. When provided, cache hits
                   return immediately with zero API calls.

        Raises:
            ImportError: If the ``anthropic`` package is not installed.
        """
        try:
            import anthropic  # noqa: PLC0415

            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AI composition. Install with: pip install bricks[ai]"
            ) from exc

        self._model = model
        self._selector = selector or AllBricksSelector()
        self._loader = BlueprintLoader()
        self._store = store

    def compose(self, task: str, registry: BrickRegistry) -> ComposeResult:
        """Compose a Blueprint YAML for a task.

        Flow:
        0. If store is configured, check for a cached blueprint by fingerprint.
           On hit: return immediately with ``cache_hit=True`` and zero tokens.
        1. selector.select(task, registry) → small pool
        2. Build system prompt with compact brick signatures from pool
        3. Single API call: task → YAML text
        4. Parse YAML → validate → return
        5. If validation fails, ONE retry with error message (fresh call)
        6. If result is valid, auto-save to store (name collision silently adds fingerprint).

        Args:
            task: Natural language task description.
            registry: BrickRegistry with available bricks.

        Returns:
            ComposeResult with blueprint YAML, validation status, and token usage.

        Raises:
            ComposerError: If the API call itself fails (network error, etc.).
        """
        # Cache check
        if self._store is not None:
            from bricks.store.models import task_fingerprint  # noqa: PLC0415

            fp = task_fingerprint(task)
            cached = self._store.get_by_fingerprint(fp)
            if cached is not None:
                self._store.touch(cached.name)
                return ComposeResult(
                    task=task,
                    blueprint_yaml=cached.yaml,
                    is_valid=True,
                    api_calls=0,
                    model=self._model,
                    cache_hit=True,
                )

        t0 = time.monotonic()
        pool = self._selector.select(task, registry)
        signatures = compact_brick_signatures(pool)
        keys_table = output_key_table(pool)
        example = _build_example(pool)
        system = _COMPOSE_SYSTEM.format(
            signatures=signatures,
            output_keys=keys_table,
            example=example,
        )
        validator = BlueprintValidator(registry=pool)

        calls: list[CallDetail] = []

        # First call
        detail = self._compose_call(1, system, task, validator)
        calls.append(detail)

        # Retry on failure (fresh call, no history)
        if not detail.is_valid and len(calls) < _MAX_API_CALLS:
            retry_prompt = _RETRY_PROMPT.format(
                task=task,
                yaml=detail.yaml_text,
                errors="\n".join(f"- {e}" for e in detail.validation_errors),
            )
            detail = self._compose_call(2, system, retry_prompt, validator)
            calls.append(detail)

        last = calls[-1]
        total_input = sum(c.input_tokens for c in calls)
        total_output = sum(c.output_tokens for c in calls)
        elapsed = time.monotonic() - t0

        result = ComposeResult(
            task=task,
            blueprint_yaml=last.yaml_text,
            is_valid=last.is_valid,
            validation_errors=last.validation_errors,
            calls=calls,
            api_calls=len(calls),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            model=self._model,
            duration_seconds=elapsed,
            system_prompt=system,
        )

        # Auto-save validated blueprint to store
        if result.is_valid and self._store is not None:
            self._auto_save(task, result.blueprint_yaml)

        return result

    def _auto_save(self, task: str, blueprint_yaml: str) -> None:
        """Auto-save a validated blueprint to the store.

        On name collision, adds the task fingerprint to the existing entry
        instead of failing. Errors are suppressed to never mask compose results.

        Args:
            task: The original task text (used to compute the fingerprint).
            blueprint_yaml: The validated blueprint YAML to store.
        """
        from bricks.store.models import StoredBlueprint, task_fingerprint  # noqa: PLC0415

        if self._store is None:
            return

        fp = task_fingerprint(task)
        bp_name = _extract_blueprint_name(blueprint_yaml)
        now = datetime.now(timezone.utc)

        try:
            self._store.save(
                StoredBlueprint(
                    name=bp_name,
                    yaml=blueprint_yaml,
                    fingerprints=[fp],
                    created_at=now,
                    last_used=now,
                )
            )
        except DuplicateBlueprintError:
            # Name already in store — add fingerprint to existing entry
            existing = self._store.get_by_name(bp_name)
            if existing is not None and fp not in existing.fingerprints:
                existing.fingerprints.append(fp)
                self._store.delete(bp_name)
                self._store.save(existing)
        except Exception:  # noqa: S110
            pass  # Never let store errors propagate to callers

    def _compose_call(
        self,
        call_number: int,
        system: str,
        user_message: str,
        validator: BlueprintValidator,
    ) -> CallDetail:
        """Make one API call, validate, and return a CallDetail.

        Args:
            call_number: 1 for first attempt, 2 for retry.
            system: System prompt.
            user_message: User message (task or retry prompt).
            validator: BlueprintValidator to check the result.

        Returns:
            CallDetail with per-call tokens, YAML, and validation status.
        """
        call_t0 = time.monotonic()
        yaml_text, in_tok, out_tok = self._call_api(system, user_message)
        is_valid, errors = self._validate_yaml(yaml_text, validator)
        call_elapsed = time.monotonic() - call_t0

        return CallDetail(
            call_number=call_number,
            system_prompt=system,
            user_prompt=user_message,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            duration_seconds=call_elapsed,
            yaml_text=yaml_text,
            is_valid=is_valid,
            validation_errors=errors,
        )

    def _call_api(self, system: str, user_message: str) -> tuple[str, int, int]:
        """Make a single API call and return (yaml_text, input_tokens, output_tokens).

        Args:
            system: System prompt.
            user_message: User message (task or retry prompt).

        Returns:
            Tuple of (extracted YAML text, input tokens, output tokens).

        Raises:
            ComposerError: If the API call fails or returns no text.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            raise ComposerError(f"API call failed: {exc}", cause=exc) from exc

        in_tok: int = response.usage.input_tokens
        out_tok: int = response.usage.output_tokens

        raw_text = self._extract_text(response)
        yaml_text = strip_code_fence(raw_text)
        return yaml_text, in_tok, out_tok

    def _validate_yaml(self, yaml_text: str, validator: BlueprintValidator) -> tuple[bool, list[str]]:
        """Parse and validate a YAML string.

        Args:
            yaml_text: Raw YAML string from the LLM.
            validator: BlueprintValidator to check against.

        Returns:
            Tuple of (is_valid, list_of_error_strings).
        """
        try:
            bp = self._loader.load_string(yaml_text)
            validator.validate(bp)
            return True, []
        except BlueprintValidationError as exc:
            return False, exc.errors
        except Exception as exc:
            return False, [str(exc)]

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
