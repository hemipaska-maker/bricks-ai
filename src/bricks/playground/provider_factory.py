"""Shared LLM-provider factory for the playground (web + CLI).

Both the FastAPI web routes and the ``bricks playground run`` CLI need
to construct an :class:`~bricks.llm.base.LLMProvider` from a
``(provider, model, api_key)`` triple. They used to diverge — the web
had its own helper inline in ``web/routes.py`` while the CLI hardcoded
``LiteLLMProvider`` and broke on every bundled preset (which all
declare ``model: claudecode``). This module is the single source of
truth.

Supported providers (matches what the web UI's dropdown exposes):

- ``claude_code`` — uses the local ``claude`` CLI session, no key
  needed.
- ``anthropic`` / ``openai`` — direct provider SDKs, BYOK required.
- ``ollama`` — local Ollama daemon, no key needed.
"""

from __future__ import annotations

import os

from bricks.llm.base import LLMProvider

#: The four providers the playground knows how to construct. Keep in
#: sync with :class:`~bricks.playground.web.schemas.RunRequest`'s
#: ``provider`` Literal so the wire format and the factory don't drift.
SUPPORTED_PROVIDERS = ("claude_code", "anthropic", "openai", "ollama")

# Providers that don't require BYOK — claude_code uses the local CLI
# session, ollama hits a local daemon. Centralised so callers can
# decide whether to prompt for / require an API key without
# reimplementing the rule.
_NO_KEY_PROVIDERS = frozenset({"claude_code", "ollama"})

# Per-provider env-var fallbacks for the API key. Resolution order in
# :func:`resolve_api_key`: explicit arg → ``BRICKS_API_KEY`` (umbrella)
# → provider-specific. The umbrella var lets a user keep one key set
# in their shell and switch providers at the CLI without re-exporting.
_PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def infer_provider(model: str) -> str:
    """Guess the provider name from a model alias.

    Used by the CLI when the user runs ``bricks playground run`` with
    only the scenario's ``model`` field to go on. The web UI doesn't
    need this — its dropdown asks for both provider and model
    explicitly.

    Heuristics, in order:

    - ``"claudecode"`` / ``"claude-code"`` / ``"claude_code"`` →
      ``claude_code``
    - ``"ollama/..."`` → ``ollama``
    - starts with ``"gpt"`` or ``"o1"`` / ``"o3"`` / ``"o4"`` →
      ``openai``
    - starts with ``"claude"`` (e.g. ``claude-haiku-4-5``) →
      ``anthropic``

    Args:
        model: Model identifier from the scenario YAML or CLI flag.

    Returns:
        One of :data:`SUPPORTED_PROVIDERS`.

    Raises:
        ValueError: If *model* doesn't match any known pattern. Caller
            should ask the user to pass ``--provider`` explicitly.
    """
    normalised = model.lower().replace("-", "").replace("_", "")
    if normalised == "claudecode":
        return "claude_code"
    if model.lower().startswith("ollama/"):
        return "ollama"
    if model.lower().startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if model.lower().startswith("claude"):
        return "anthropic"
    raise ValueError(
        f"Cannot infer provider from model {model!r}. "
        f"Pass --provider explicitly (one of {', '.join(SUPPORTED_PROVIDERS)})."
    )


def resolve_api_key(provider: str, explicit: str = "") -> str:
    """Pick an API key for *provider* in the agreed precedence order.

    Order: ``explicit`` (CLI flag or web request body) →
    ``BRICKS_API_KEY`` env (provider-agnostic umbrella) →
    provider-specific env (``ANTHROPIC_API_KEY`` /
    ``OPENAI_API_KEY``).

    Args:
        provider: One of :data:`SUPPORTED_PROVIDERS`.
        explicit: User-supplied key. Empty string means "fall through
            to env vars".

    Returns:
        The resolved key, or ``""`` for providers that don't need one
        (claude_code, ollama). Returns ``""`` rather than raising when
        no key is found; the caller decides whether the empty result
        is a hard error.
    """
    if provider in _NO_KEY_PROVIDERS:
        return ""
    if explicit:
        return explicit
    umbrella = os.environ.get("BRICKS_API_KEY", "")
    if umbrella:
        return umbrella
    env_var = _PROVIDER_ENV_KEYS.get(provider, "")
    return os.environ.get(env_var, "") if env_var else ""


def build_provider(provider: str, model: str, api_key: str = "") -> LLMProvider:
    """Construct an :class:`~bricks.llm.base.LLMProvider` from a triple.

    Args:
        provider: One of :data:`SUPPORTED_PROVIDERS`.
        model: Provider-specific model identifier (e.g.
            ``claude-haiku-4-5``, ``gpt-4o-mini``, ``ollama/llama3``).
            For ``claude_code``, an empty string is allowed — the
            ``claude`` CLI picks its own default.
        api_key: BYOK key. Required for ``anthropic`` / ``openai``,
            ignored for ``claude_code`` and ``ollama``.

    Returns:
        An :class:`LLMProvider` ready for the engine to call.

    Raises:
        ValueError: If *provider* is unknown OR if BYOK is required but
            *api_key* is empty. The web layer wraps this in an
            ``HTTPException(400)`` at the route boundary; the CLI lets
            it surface as a non-zero exit with the message printed.
    """
    if provider == "claude_code":
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(model=model or None)

    if provider == "ollama":
        from bricks.providers.ollama import OllamaProvider

        return OllamaProvider(model=model)

    if provider in {"anthropic", "openai"} and not api_key:
        raise ValueError(
            f"{provider} requires an api_key (--api-key, BRICKS_API_KEY, or {_PROVIDER_ENV_KEYS[provider]})"
        )

    if provider == "anthropic":
        from bricks.providers.anthropic import AnthropicProvider

        return AnthropicProvider(model=model, api_key=api_key)

    if provider == "openai":
        from bricks.providers.openai import OpenAIProvider

        return OpenAIProvider(model=model, api_key=api_key)

    raise ValueError(f"Unknown provider {provider!r}; expected one of {SUPPORTED_PROVIDERS}")
