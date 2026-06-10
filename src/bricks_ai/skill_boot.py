"""Markdown skill bootstrapping — one LLM call to extract domain config.

The deterministic engine boots from ``agent.yaml`` only (see
:class:`~bricks.boot.bootstrapper.SystemBootstrapper`). Free-text
``skill.md`` descriptions need an LLM to extract ``brick_categories`` and
``tags``, so that path lives here in the AI layer.
"""

from __future__ import annotations

import json
from pathlib import Path

from bricks.boot.config import SystemConfig
from bricks_ai.llm.base import LLMProvider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_EXTRACT_SYSTEM = """\
You are a configuration extractor. Given an agent description, extract the domain categories and tags.
Return ONLY valid JSON with no explanation:
{"categories": ["category1", "category2"], "tags": ["tag1", "tag2"]}

Categories should be snake_case domain areas (e.g. data_transformation, string_processing, math, date_time).
Tags should be concise descriptive labels (e.g. aggregation, filtering, formatting).
"""


def bootstrap_from_skill(
    skill_path: Path,
    *,
    api_key: str = "",
    model: str = _DEFAULT_MODEL,
    provider: LLMProvider | None = None,
) -> SystemConfig:
    """Parse a ``skill.md`` file, making one LLM call to extract config.

    Args:
        skill_path: Path to the markdown skill description.
        api_key: API key for the default LiteLLM provider. Ignored when an
            explicit ``provider`` is given.
        model: Model ID used for the extraction call (default provider only).
        provider: Optional custom LLM provider.

    Returns:
        A ``SystemConfig`` with ``brick_categories`` and ``tags`` extracted
        by the LLM. Falls back to empty lists on any LLM or parse error.

    Raises:
        FileNotFoundError: If ``skill_path`` does not exist.
        ValueError: If the file extension is not ``.md``.
    """
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")
    if skill_path.suffix.lower() != ".md":
        raise ValueError(f"Unsupported skill format {skill_path.suffix!r}. Use '.md'.")
    content = skill_path.read_text(encoding="utf-8")
    name = _extract_md_title(content) or skill_path.stem
    categories, tags = _extract_from_llm(content, api_key=api_key, model=model, provider=provider)
    return SystemConfig(
        name=name,
        description=content[:500],
        brick_categories=categories,
        tags=tags,
        model=model,
        api_key=api_key,
    )


def _extract_from_llm(
    description: str,
    *,
    api_key: str,
    model: str,
    provider: LLMProvider | None,
) -> tuple[list[str], list[str]]:
    """Call the LLM to extract categories and tags from a description.

    Args:
        description: Agent description text.
        api_key: API key for the default LiteLLM provider.
        model: Model ID for the extraction call.
        provider: Optional custom LLM provider.

    Returns:
        A tuple of ``(categories, tags)`` lists. Falls back to ``([], [])``
        on any error so skill bootstrapping never raises on LLM failures.
    """
    try:
        from bricks_ai.llm.litellm_provider import LiteLLMProvider  # noqa: PLC0415

        resolved = provider or LiteLLMProvider(model=model, api_key=api_key)
        text = resolved.complete(prompt=description, system=_EXTRACT_SYSTEM).text.strip()
        parsed = json.loads(text)
        categories = [str(c) for c in parsed.get("categories", [])]
        tags = [str(t) for t in parsed.get("tags", [])]
        return categories, tags
    except Exception:
        return [], []


def _extract_md_title(content: str) -> str:
    """Extract the first H1 heading from markdown content.

    Args:
        content: Markdown text.

    Returns:
        The heading text without the leading ``#``, or empty string if not found.
    """
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""
