"""Bricks core: engine, context, validation, and Brick base classes."""

from bricks.core.brick import BaseBrick, BrickModel, brick
from bricks.core.catalog import TieredCatalog
from bricks.core.config import (
    AiConfig,
    BlueprintsConfig,
    BricksConfig,
    CatalogConfig,
    ConfigLoader,
    RegistryConfig,
)
from bricks.core.context import ExecutionContext
from bricks.core.discovery import BrickDiscovery
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import (
    BlueprintValidationError,
    BrickError,
    BrickExecutionError,
    BrickNotFoundError,
    ConfigError,
    DuplicateBrickError,
    VariableResolutionError,
    YamlLoadError,
)
from bricks.core.loader import BlueprintLoader
from bricks.core.models import (
    BlueprintDefinition,
    BrickMeta,
    ExecutionResult,
    StepDefinition,
    StepResult,
    Verbosity,
)
from bricks.core.registry import BrickRegistry
from bricks.core.resolver import ReferenceResolver
from bricks.core.schema import blueprint_schema, brick_schema, catalog_schema, registry_schema
from bricks.core.utils import blueprint_to_yaml
from bricks.core.validation import BlueprintValidator

# Deprecated aliases — will be removed in v1.0.0
SequenceDefinition = BlueprintDefinition
SequenceEngine = BlueprintEngine
SequenceLoader = BlueprintLoader
SequenceValidator = BlueprintValidator
SequenceValidationError = BlueprintValidationError
SequencesConfig = BlueprintsConfig
sequence_schema = blueprint_schema
sequence_to_yaml = blueprint_to_yaml

__all__ = [
    "AiConfig",
    "BaseBrick",
    "BlueprintDefinition",
    "BlueprintEngine",
    "BlueprintLoader",
    "BlueprintValidationError",
    "BlueprintValidator",
    "BlueprintsConfig",
    "BrickDiscovery",
    "BrickError",
    "BrickExecutionError",
    "BrickMeta",
    "BrickModel",
    "BrickNotFoundError",
    "BrickRegistry",
    "BricksConfig",
    "CatalogConfig",
    "ConfigError",
    "ConfigLoader",
    "DuplicateBrickError",
    "ExecutionContext",
    "ExecutionResult",
    "ReferenceResolver",
    "RegistryConfig",
    # Deprecated aliases — will be removed in v1.0.0
    "SequenceDefinition",
    "SequenceEngine",
    "SequenceLoader",
    "SequenceValidationError",
    "SequenceValidator",
    "SequencesConfig",
    "StepDefinition",
    "StepResult",
    "TieredCatalog",
    "VariableResolutionError",
    "Verbosity",
    "YamlLoadError",
    "blueprint_schema",
    "blueprint_to_yaml",
    "brick",
    "brick_schema",
    "catalog_schema",
    "registry_schema",
    "sequence_schema",
    "sequence_to_yaml",
]
