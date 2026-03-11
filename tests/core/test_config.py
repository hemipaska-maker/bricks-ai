"""Tests for bricks.core.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from bricks.core.config import BricksConfig, ConfigLoader
from bricks.core.exceptions import ConfigError


class TestDefaultConfig:
    def test_default_config_is_valid(self) -> None:
        config = BricksConfig()
        assert config.version == "1"
        assert config.registry.auto_discover is False
        assert config.registry.paths == []
        assert config.sequences.base_dir == "sequences/"
        assert config.ai.model == "claude-3-5-haiku-latest"
        assert config.ai.max_tokens == 4096

    def test_load_returns_default_when_no_file(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        config = loader.load(directory=tmp_path)
        assert isinstance(config, BricksConfig)
        assert config.registry.auto_discover is False


class TestLoadString:
    def test_load_full_config(self) -> None:
        loader = ConfigLoader()
        yaml_content = """
version: "1"
registry:
  auto_discover: true
  paths:
    - "bricks_lib/"
    - "custom_bricks.py"
sequences:
  base_dir: "my_sequences/"
ai:
  model: "claude-3-5-haiku-latest"
  max_tokens: 2048
"""
        config = loader.load_string(yaml_content)
        assert config.version == "1"
        assert config.registry.auto_discover is True
        assert config.registry.paths == ["bricks_lib/", "custom_bricks.py"]
        assert config.sequences.base_dir == "my_sequences/"
        assert config.ai.model == "claude-3-5-haiku-latest"
        assert config.ai.max_tokens == 2048

    def test_load_partial_config_uses_defaults(self) -> None:
        loader = ConfigLoader()
        config = loader.load_string("registry:\n  auto_discover: true\n")
        assert config.registry.auto_discover is True
        assert config.ai.max_tokens == 4096  # default preserved

    def test_empty_yaml_returns_default(self) -> None:
        loader = ConfigLoader()
        config = loader.load_string("")
        assert isinstance(config, BricksConfig)

    def test_invalid_yaml_raises_config_error(self) -> None:
        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load_string("invalid: yaml: [unclosed")

    def test_wrong_type_raises_config_error(self) -> None:
        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load_string("- this\n- is\n- a list\n")


class TestLoadFile:
    def test_load_file_reads_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bricks.config.yaml"
        config_file.write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'bricks/'\n"
        )
        loader = ConfigLoader()
        config = loader.load_file(config_file)
        assert config.registry.auto_discover is True
        assert config.registry.paths == ["bricks/"]

    def test_load_file_raises_for_missing_file(self, tmp_path: Path) -> None:
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file(tmp_path / "nonexistent.yaml")

    def test_load_searches_for_default_filename(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bricks.config.yaml"
        config_file.write_text("ai:\n  max_tokens: 1000\n")
        loader = ConfigLoader()
        config = loader.load(directory=tmp_path)
        assert config.ai.max_tokens == 1000


class TestConfigError:
    def test_config_error_message_includes_path(self) -> None:
        err = ConfigError("/path/to/config.yaml", ValueError("bad value"))
        assert "/path/to/config.yaml" in str(err)
        assert err.path == "/path/to/config.yaml"
