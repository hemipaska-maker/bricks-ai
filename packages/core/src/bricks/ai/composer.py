"""AI blueprint composer: single-call Python DSL generation from natural language.

No tool_use, no multi-turn conversation. The LLM outputs Python DSL code as
plain text, which we validate with an AST whitelist and execute in a
restricted namespace to produce a FlowDefinition.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from bricks.core.dsl import FlowDefinition, branch, flow, for_each, step
from bricks.core.exceptions import BlueprintValidationError, BrickError, DuplicateBlueprintError
from bricks.core.registry import BrickRegistry
from bricks.core.schema import compact_brick_signatures
from bricks.core.selector import AllBricksSelector, BrickSelector
from bricks.core.validator_dsl import validate_dsl
from bricks.llm.base import LLMProvider

if TYPE_CHECKING:
    from bricks.store.blueprint_store import BlueprintStore

logger = logging.getLogger(__name__)


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


class CompositionError(ComposerError):
    """Raised when LLM-generated DSL code is invalid or cannot be executed."""


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: str
    blueprint_yaml: str = ""
    dsl_code: str = ""
    flow_def: FlowDefinition | None = None
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


# System prompt — instructs the LLM to produce Python DSL instead of YAML.
DSL_PROMPT_TEMPLATE = """\
You are a Blueprint composer for the Bricks framework. Generate ONLY valid Python code using the DSL.

Available bricks:
{brick_signatures}

Available primitives:
- step.brick_name(param=value) → captures a brick invocation
- for_each(items, do=lambda item: step.brick(...), on_error="fail"|"collect") → maps a step over a list
- branch(condition="brick_name", if_true=lambda: step.X(...), if_false=lambda: step.Y(...)) → conditional routing

Rules:
1. Write a single function decorated with @flow
2. Function name should describe the task (e.g., def clean_and_process)
3. NO imports — step, for_each, branch, flow are pre-provided
4. NO if/for/while/class/try — use branch() and for_each() instead
5. Only use step.brick_name() for brick calls — brick names must match the available bricks list above
6. Parameters must be keyword-only: step.clean(text=data) NOT step.clean(data)
7. You can assign step results to variables and pass them to other steps
8. Return the final step result
9. on_error="fail" (default) stops on first error. on_error="collect" continues and gathers errors.
10. branch condition must be a brick name string that returns boolean

Task: {task}
{input_context}
Output ONLY the Python code. No markdown fences. No explanation.\
"""

_RETRY_PROMPT = """\
Original task:
{task}

The following DSL code has validation errors:

{code}

Errors:
{errors}

Output ONLY the corrected Python code. Nothing else.\
"""

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2048
_MAX_API_CALLS = 2


def _build_input_context(input_keys: list[str] | None) -> str:
    """Build an input hint line for the prompt.

    Args:
        input_keys: Optional list of known input key names.

    Returns:
        A one-line hint string, or empty string if no keys given.
    """
    if not input_keys:
        return ""
    keys_str = ", ".join(input_keys)
    return f"The function receives these parameters: {keys_str}.\n"


class BlueprintComposer:
    """Composes Blueprint DSL from a natural language task using a single LLM call.

    No tool_use, no multi-turn conversation. The LLM outputs Python DSL code,
    which is validated with an AST whitelist and executed in a restricted
    namespace to produce a FlowDefinition and BlueprintDefinition.

    If the first attempt fails validation, makes ONE retry with a fresh
    prompt containing the errors. Max 2 API calls total.

    Args:
        provider: LLM provider used for blueprint generation.
        selector: BrickSelector for Stage 1 filtering (default: AllBricksSelector).
        store: Optional blueprint store for caching.
    """

    _provider: LLMProvider

    def __init__(
        self,
        provider: LLMProvider,
        selector: BrickSelector | None = None,
        store: BlueprintStore | None = None,
    ) -> None:
        """Initialise the composer.

        Args:
            provider: LLM provider used for blueprint generation.
            selector: BrickSelector for Stage 1 filtering. Defaults to AllBricksSelector.
            store: Optional blueprint store for caching. When provided, cache hits
                   return immediately with zero API calls.
        """
        self._provider = provider
        self._selector = selector or AllBricksSelector()
        self._store = store

    def compose(
        self,
        task: str,
        registry: BrickRegistry,
        input_keys: list[str] | None = None,
    ) -> ComposeResult:
        """Compose a Blueprint from a natural language task using Python DSL.

        Flow:
        0. If store is configured, check for a cached blueprint by fingerprint.
           On hit: return immediately with ``cache_hit=True`` and zero tokens.
        1. selector.select(task, registry) → small pool
        2. Build system prompt with compact brick signatures from pool
        3. Single API call: task → DSL code
        4. Validate DSL with AST whitelist; if valid, exec and extract FlowDefinition
        5. If validation fails, ONE retry with error message (fresh call)
        6. If result is valid, auto-save to store.

        Args:
            task: Natural language task description.
            registry: BrickRegistry with available bricks.
            input_keys: Optional list of user-supplied input key names.

        Returns:
            ComposeResult with DSL code, blueprint YAML, validation status, and token usage.

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
                logger.info("Cache hit for task fingerprint %s", fp)
                return ComposeResult(
                    task=task,
                    blueprint_yaml=cached.yaml,
                    is_valid=True,
                    api_calls=0,
                    model="",
                    cache_hit=True,
                )

        t0 = time.monotonic()
        pool = self._selector.select(task, registry)
        logger.info(
            "Composing blueprint for task (%d chars), %d bricks in pool",
            len(task),
            len(pool.list_all()),
        )

        signatures = compact_brick_signatures(pool)
        system = DSL_PROMPT_TEMPLATE.format(
            brick_signatures=signatures,
            task=task,
            input_context=_build_input_context(input_keys),
        )

        calls: list[CallDetail] = []

        # Build user message
        user_message = task
        if input_keys:
            keys_str = ", ".join(input_keys)
            user_message = f"{task}\nThe function receives these parameters: {keys_str}."

        # First call
        detail = self._compose_call(1, system, user_message)
        calls.append(detail)

        # Retry on failure
        if not detail.is_valid and len(calls) < _MAX_API_CALLS:
            retry_prompt = _RETRY_PROMPT.format(
                task=task,
                code=detail.yaml_text,
                errors="\n".join(f"- {e}" for e in detail.validation_errors),
            )
            detail = self._compose_call(2, system, retry_prompt)
            calls.append(detail)

        last = calls[-1]
        total_input = sum(c.input_tokens for c in calls)
        total_output = sum(c.output_tokens for c in calls)
        elapsed = time.monotonic() - t0

        blueprint_yaml = ""
        dsl_code = ""
        flow_def: FlowDefinition | None = None
        if last.is_valid:
            flow_def = self._parse_dsl_response(last.yaml_text)
            blueprint_yaml = flow_def.to_yaml()
            dsl_code = self._strip_fences(last.yaml_text)

        result = ComposeResult(
            task=task,
            blueprint_yaml=blueprint_yaml,
            dsl_code=dsl_code,
            flow_def=flow_def,
            is_valid=last.is_valid,
            validation_errors=last.validation_errors,
            calls=calls,
            api_calls=len(calls),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            model="",
            duration_seconds=elapsed,
            system_prompt=system,
        )

        logger.info(
            "Compose complete: valid=%s, %d calls, %.1fs",
            result.is_valid,
            result.api_calls,
            result.duration_seconds,
        )

        # Auto-save validated blueprint to store
        if result.is_valid and self._store is not None and flow_def is not None:
            self._auto_save(task, flow_def.name, blueprint_yaml)

        return result

    def _auto_save(self, task: str, blueprint_name: str, blueprint_yaml: str) -> None:
        """Auto-save a validated blueprint to the store.

        On name collision, adds the task fingerprint to the existing entry
        instead of failing. Errors are suppressed to never mask compose results.

        Args:
            task: The original task text (used to compute the fingerprint).
            blueprint_name: Name from the FlowDefinition.
            blueprint_yaml: The validated blueprint YAML to store.
        """
        from bricks.store.models import StoredBlueprint, task_fingerprint  # noqa: PLC0415

        if self._store is None:
            return

        fp = task_fingerprint(task)
        now = datetime.now(timezone.utc)

        try:
            self._store.save(
                StoredBlueprint(
                    name=blueprint_name,
                    yaml=blueprint_yaml,
                    fingerprints=[fp],
                    created_at=now,
                    last_used=now,
                )
            )
        except DuplicateBlueprintError:
            existing = self._store.get_by_name(blueprint_name)
            if existing is not None and fp not in existing.fingerprints:
                existing.fingerprints.append(fp)
                self._store.delete(blueprint_name)
                self._store.save(existing)
        except Exception:  # noqa: S110
            pass

    def _compose_call(
        self,
        call_number: int,
        system: str,
        user_message: str,
    ) -> CallDetail:
        """Make one API call, validate the DSL, and return a CallDetail.

        Args:
            call_number: 1 for first attempt, 2 for retry.
            system: System prompt.
            user_message: User message (task or retry prompt).

        Returns:
            CallDetail with per-call tokens, raw code, and validation status.
        """
        logger.info(
            "Compose call #%d: system=%d chars, user=%d chars",
            call_number,
            len(system),
            len(user_message),
        )

        call_t0 = time.monotonic()
        raw_text, in_tok, out_tok = self._make_api_call(system, user_message)
        is_valid, errors = self._validate_dsl_text(raw_text)
        call_elapsed = time.monotonic() - call_t0

        logger.info(
            "Compose call #%d: valid=%s, code=%d chars, %.1fs",
            call_number,
            is_valid,
            len(raw_text),
            call_elapsed,
        )
        if not is_valid:
            logger.warning("Compose call #%d validation failed: %s", call_number, errors)

        return CallDetail(
            call_number=call_number,
            system_prompt=system,
            user_prompt=user_message,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            duration_seconds=call_elapsed,
            yaml_text=raw_text,
            is_valid=is_valid,
            validation_errors=errors,
        )

    def _make_api_call(self, system: str, user_message: str) -> tuple[str, int, int]:
        """Make a single LLM call and return (raw_text, input_tokens, output_tokens).

        Args:
            system: System prompt.
            user_message: User message.

        Returns:
            Tuple of (raw text from LLM, input tokens, output tokens).

        Raises:
            ComposerError: If the API call fails or returns no text.
        """
        from bricks.errors import BricksComposeError, BricksConfigError  # noqa: PLC0415

        try:
            completion = self._provider.complete(prompt=user_message, system=system)
        except (BricksConfigError, BricksComposeError):
            raise
        except Exception as exc:
            logger.error("API call failed: %s", exc, exc_info=True)
            raise ComposerError(f"API call failed: {exc}", cause=exc) from exc
        return completion.text, completion.input_tokens, completion.output_tokens

    def _validate_dsl_text(self, code: str) -> tuple[bool, list[str]]:
        """Run AST whitelist validation on raw DSL text (strips fences first).

        Args:
            code: Raw LLM output, possibly with markdown fences.

        Returns:
            Tuple of (is_valid, list_of_error_strings).
        """
        cleaned = self._strip_fences(code)
        result = validate_dsl(cleaned)
        return result.valid, result.errors

    def _parse_dsl_response(self, raw_code: str) -> FlowDefinition:
        """Parse and validate LLM-generated Python DSL code.

        Steps:
        1. Strip markdown fences if present
        2. Validate with PythonDSLValidator
        3. Execute in restricted namespace
        4. Return the FlowDefinition

        Args:
            raw_code: Raw LLM output string.

        Returns:
            FlowDefinition produced by the @flow decorator.

        Raises:
            CompositionError: If AST validation fails or no FlowDefinition is produced.
        """
        code = self._strip_fences(raw_code)

        validation = validate_dsl(code)
        if not validation.valid:
            raise CompositionError(f"LLM generated invalid DSL code. Errors: {validation.errors}\nCode:\n{code}")

        namespace: dict[str, Any] = {
            "step": step,
            "for_each": for_each,
            "branch": branch,
            "flow": flow,
        }
        exec(code, namespace)  # noqa: S102 — safe: AST-validated above

        flow_def = next(
            (v for v in namespace.values() if isinstance(v, FlowDefinition)),
            None,
        )
        if flow_def is None:
            raise CompositionError(f"LLM code did not produce a FlowDefinition.\nCode:\n{code}")

        return flow_def

    @staticmethod
    def _strip_fences(code: str) -> str:
        """Remove markdown code fences from LLM output.

        Args:
            code: Raw text that may be wrapped in ```python ... ``` or ``` ... ```.

        Returns:
            Code with fence lines removed and surrounding whitespace stripped.
        """
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            code = "\n".join(lines)
        return code.strip()

    def _validate_yaml(self, yaml_text: str, validator: Any) -> tuple[bool, list[str]]:
        """Legacy YAML validation — kept for internal use only.

        Args:
            yaml_text: Raw YAML string.
            validator: BlueprintValidator instance.

        Returns:
            Tuple of (is_valid, error_strings).
        """
        from bricks.core.loader import BlueprintLoader  # noqa: PLC0415

        loader = BlueprintLoader()
        try:
            bp = loader.load_string(yaml_text)
            validator.validate(bp)
            return True, []
        except BlueprintValidationError as exc:
            return False, exc.errors
        except Exception as exc:
            return False, [str(exc)]
