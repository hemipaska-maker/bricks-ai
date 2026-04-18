"""SystemBootstrapper: reads agent.yaml or skill.md, returns SystemConfig.

``agent.yaml`` → parse directly, zero LLM calls.
``skill.md``   → one LLM call to extract categories and tags, then build config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from bricks.boot.config import SystemConfig
from bricks.core.config import StoreConfig
from bricks.llm.base import LLMProvider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_EXTRACT_SYSTEM = """\
You are a configuration extractor. Given an agent description, extract the domain categories and tags.
Return ONLY valid JSON with no explanation:
{"categories": ["category1", "category2"], "tags": ["tag1", "tag2"]}

Categories should be snake_case domain areas (e.g. data_transformation, string_processing, math, date_time).
Tags should be concise descriptive labels (e.g. aggregation, filtering, formatting).
"""


class SystemBootstrapper:
    """Reads a config file and returns a fully resolved ``SystemConfig``.

    Supports two config formats:

    - ``agent.yaml``: structured YAML, parsed directly without any LLM call.
    - ``skill.md``: free-text markdown description; one LLM call extracts
      ``brick_categories`` and ``tags`` from the description.

    If the LLM call fails or returns unparseable JSON, the bootstrapper falls
    back to empty ``categories`` and ``tags`` — it never raises on LLM errors.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = _DEFAULT_MODEL,
        provider: LLMProvider | None = None,
    ) -> None:
        """Initialise the bootstrapper.

        Args:
            api_key: API key for the default LiteLLM provider. Required only for ``.md`` files
                when no explicit ``provider`` is given.
            model: Model ID used for the extraction call (default LiteLLM provider only).
            provider: Optional custom LLM provider. When given, ``api_key`` and ``model``
                are ignored for LLM calls.
        """
        self._api_key = api_key
        self._model = model
        self._provider = provider
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def bootstrap(self, config_path: Path) -> SystemConfig:
        """Read a config file and return a resolved ``SystemConfig``.

        Args:
            config_path: Path to ``agent.yaml`` or ``skill.md``.

        Returns:
            A populated ``SystemConfig``.

        Raises:
            FileNotFoundError: If ``config_path`` does not exist.
            ValueError: If the file extension is not ``.yaml`` or ``.md``.
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        suffix = config_path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            return self._from_yaml(config_path)
        if suffix == ".md":
            return self._from_markdown(config_path)
        raise ValueError(f"Unsupported config format {suffix!r}. Use '.yaml' or '.md'.")

    # ── private helpers ────────────────────────────────────────────────────

    def _from_yaml(self, path: Path) -> SystemConfig:
        """Parse an ``agent.yaml`` file into a ``SystemConfig``.

        Args:
            path: Path to the YAML config file.

        Returns:
            A validated ``SystemConfig``.

        Raises:
            ValueError: If the YAML is malformed or missing required fields.
        """
        try:
            data: Any = self._yaml.load(path.read_text(encoding="utf-8"))
        except YAMLError as exc:
            raise ValueError(f"YAML parse error in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Expected YAML mapping in {path}, got {type(data).__name__}")

        store_raw = data.get("store", {})
        store_cfg = StoreConfig.model_validate(store_raw) if store_raw else StoreConfig()

        return SystemConfig(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            brick_categories=data.get("brick_categories", []),
            tags=data.get("tags", []),
            model=data.get("model", _DEFAULT_MODEL),
            api_key=data.get("api_key", self._api_key),
            store=store_cfg,
            max_selector_results=data.get("max_selector_results", 20),
        )

    def _from_markdown(self, path: Path) -> SystemConfig:
        """Parse a ``skill.md`` file, making one LLM call to extract config.

        Args:
            path: Path to the markdown file.

        Returns:
            A ``SystemConfig`` with ``brick_categories`` and ``tags`` extracted
            by the LLM. Falls back to empty lists on any LLM or parse error.
        """
        content = path.read_text(encoding="utf-8")
        name = _extract_md_title(content) or path.stem
        categories, tags = self._extract_from_llm(content)
        return SystemConfig(
            name=name,
            description=content[:500],
            brick_categories=categories,
            tags=tags,
            model=self._model,
            api_key=self._api_key,
        )

    def _extract_from_llm(self, description: str) -> tuple[list[str], list[str]]:
        """Call the LLM to extract categories and tags from a description.

        Args:
            description: Agent description text.

        Returns:
            A tuple of ``(categories, tags)`` lists. Falls back to ``([], [])``
            on any error so the bootstrapper never raises on LLM failures.
        """
        try:
            from bricks.llm.litellm_provider import LiteLLMProvider  # noqa: PLC0415

            provider = self._provider or LiteLLMProvider(model=self._model, api_key=self._api_key)
            text = provider.complete(prompt=description, system=_EXTRACT_SYSTEM).text.strip()
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
