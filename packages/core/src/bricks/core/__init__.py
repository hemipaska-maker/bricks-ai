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
    SelectorConfig,
    StoreConfig,
)
from bricks.core.context import ExecutionContext
from bricks.core.dag import DAG
from bricks.core.dag_builder import DAGBuilder
from bricks.core.discovery import BrickDiscovery
from bricks.core.dsl import ExecutionTracer, Node, StepProxy, branch, for_each, step
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import (
    BlueprintValidationError,
    BrickError,
    BrickExecutionError,
    BrickNotFoundError,
    ConfigError,
    DuplicateBlueprintError,
    DuplicateBrickError,
    OrchestratorError,
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
from bricks.core.schema import (
    blueprint_schema,
    brick_schema,
    catalog_schema,
    output_key_table,
    output_keys,
    parse_description_keys,
    registry_schema,
    signature_params,
)
from bricks.core.selector import AllBricksSelector, BrickSelector
from bricks.core.utils import blueprint_to_yaml
from bricks.core.validation import BlueprintValidator
from bricks.selector import BrickQuery, TieredBrickSelector

# Deprecated aliases — use bricks.compat for warnings, these are kept
# for backward compatibility and will be removed in v1.0.0
SequenceDefinition = BlueprintDefinition
SequenceEngine = BlueprintEngine
SequenceLoader = BlueprintLoader
SequenceValidator = BlueprintValidator
SequenceValidationError = BlueprintValidationError
SequencesConfig = BlueprintsConfig
sequence_schema = blueprint_schema
sequence_to_yaml = blueprint_to_yaml

__all__ = [
    "DAG",
    "AiConfig",
    "AllBricksSelector",
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
    "BrickQuery",
    "BrickRegistry",
    "BrickSelector",
    "BricksConfig",
    "CatalogConfig",
    "ConfigError",
    "ConfigLoader",
    "DAGBuilder",
    "DuplicateBlueprintError",
    "DuplicateBrickError",
    "ExecutionContext",
    "ExecutionResult",
    "ExecutionTracer",
    "Node",
    "OrchestratorError",
    "ReferenceResolver",
    "RegistryConfig",
    "SelectorConfig",
    "StepDefinition",
    "StepProxy",
    "StepResult",
    "StoreConfig",
    "TieredBrickSelector",
    "TieredCatalog",
    "VariableResolutionError",
    "Verbosity",
    "YamlLoadError",
    "blueprint_schema",
    "blueprint_to_yaml",
    "branch",
    "brick",
    "brick_schema",
    "catalog_schema",
    "for_each",
    "output_key_table",
    "output_keys",
    "parse_description_keys",
    "registry_schema",
    "signature_params",
    "step",
]
