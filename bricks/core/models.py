"""Pydantic models for Brick metadata and YAML blueprint definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class BrickMeta(BaseModel):
    """Metadata attached to a registered Brick."""

    name: str
    tags: list[str] = Field(default_factory=list)
    destructive: bool = False
    idempotent: bool = True
    description: str = ""


class StepDefinition(BaseModel):
    """A single step within a blueprint definition (parsed from YAML).

    Each step must specify exactly one of ``brick`` (a registered brick name)
    or ``blueprint`` (a path to a child blueprint YAML file).
    """

    name: str
    brick: str | None = None
    blueprint: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    save_as: str | None = None

    @model_validator(mode="after")
    def check_brick_or_blueprint(self) -> StepDefinition:
        """Enforce exactly one of brick or blueprint is set."""
        if self.brick is None and self.blueprint is None:
            raise ValueError("Step must specify either 'brick' or 'blueprint'")
        if self.brick is not None and self.blueprint is not None:
            raise ValueError("Step cannot specify both 'brick' and 'blueprint'")
        return self


class BlueprintDefinition(BaseModel):
    """A complete blueprint definition (parsed from YAML).

    Represents the top-level structure of a blueprint YAML file.
    """

    name: str
    description: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    steps: list[StepDefinition] = Field(default_factory=list)
    outputs_map: dict[str, str] = Field(default_factory=dict)
