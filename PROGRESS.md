# Bricks Implementation Progress

## Status: Phase 9 -- Comprehensive Test Expansion + Integration (COMPLETE)

### Completed Phases
- [x] **Scaffolding** -- 14 source files, 22 tests, mypy/ruff clean, CLI stubs, example
- [x] **Phase 1: YAML Loader** -- `BlueprintLoader` with `load_file()` and `load_string()`
- [x] **Phase 2: Sub-Sequence Support** -- models + engine
- [x] **Phase 3: Enhanced Validation** -- 5 additional checks, 63 tests total (up from 42)
- [x] **Phase 4: Brick Discovery + JSON Schema** -- `BrickDiscovery`, `brick_schema`, `registry_schema`, `blueprint_schema`
- [x] **Phase 5: Configuration** -- `BricksConfig`, `ConfigLoader`, `ConfigError`, 11 new tests
- [x] **Phase 7: AI Composition Layer** -- `BlueprintComposer`, `ComposerError`, 17 new tests (145 total)

### Phase 4 Details

#### Phase 4A: Brick Discovery (`bricks/core/discovery.py`)
`BrickDiscovery` class with three discovery methods:
- `discover_module(module)` -- scans an already-imported `ModuleType` for decorated functions (`__brick_meta__`) and `BaseBrick` subclasses
- `discover_path(path)` -- dynamically imports a `.py` file and delegates to `discover_module`
- `discover_package(package_path)` -- iterates all non-underscore `.py` files in a directory and calls `discover_path` on each
- `_try_register(obj)` -- private helper that attempts to register any Python object as a brick; returns the registered name or `None`

Key behaviors:
- Skips already-registered names (no `DuplicateBrickError`)
- Skips files starting with `_` in package discovery
- Silently skips files that cannot be imported (package-level)
- Raises `FileNotFoundError` for missing `.py` paths
- Raises `NotADirectoryError` when `discover_package` receives a file path

#### Phase 4B: JSON Schema Export (`bricks/core/schema.py`)
Three public functions:
- `brick_schema(name, registry)` -- returns a dict with `name`, `description`, `tags`, `destructive`, `idempotent`, and `parameters` for a registered brick; uses `inspect.signature` to extract parameter names, type annotations, and required/optional status
- `blueprint_schema(sequence)` -- serialises a `BlueprintDefinition` to a JSON-compatible dict including all steps with their `name`, `brick`, `params`, and `save_as` fields
- `registry_schema(registry)` -- returns a sorted list of `brick_schema` dicts for all registered bricks

#### `bricks/core/__init__.py` updates
Added exports: `BrickDiscovery`, `brick_schema`, `registry_schema`, `blueprint_schema`

Also restored `YamlLoadError` and `ConfigError` to `bricks/core/exceptions.py` which were lost during a stash/restore operation (these belong to Phase 1 and Phase 5 respectively).

### Phase 3 Details
Added 5 new validation checks to `bricks/core/validation.py`:
- **Check 3**: Duplicate step name detection -- `"Duplicate step name: 'step_name'"`
- **Check 4**: `outputs_map` reference validation -- verifies values point to known `save_as` names or declared inputs
- **Check 5**: Input reference completeness -- scans `${inputs.X}` patterns in all step params (recursively through dicts/lists/strings) and verifies each X exists in `sequence.inputs`
- **Check 6**: Result reference completeness -- scans `${name}` patterns and enforces forward-reference prohibition; reports both "not yet available" (defined later) and "undefined variable" (never defined) errors
- **Check 7**: Empty sequence guard -- `"Sequence 'name' has no steps"`

New helper `_extract_references(value)` recursively scans any value (str/dict/list/primitive) for `${...}` patterns.

Test suite expanded from 1 to 22 tests in `tests/core/test_validation.py`, covering all checks with both pass and fail cases, plus edge cases (nested dict/list params, self-reference, multiple errors collected).

### Phase 5 Details

Created `bricks/core/config.py` with:
- `RegistryConfig`, `BlueprintsConfig`, `AiConfig` -- Pydantic sub-models for config sections
- `BricksConfig` -- top-level config model with defaults (version "1", auto_discover false, base_dir "blueprints/", model "claude-3-5-sonnet-20241022", max_tokens 4096)
- `ConfigLoader` -- loads from directory (auto-discovers `bricks.config.yaml`), file path, or YAML string; returns default `BricksConfig` when no file found
- `ConfigError` -- added to `bricks/core/exceptions.py` following project convention; raised on parse or validation failures

Also restored Phase 3 validation checks (checks 3-7) and `test_validation.py` (18 tests) and updated `bricks/core/__init__.py` to export all new symbols from Phases 3-5.

### Phase 6 Details

Implemented all 8 CLI commands in `bricks/cli/main.py`:
- `init` -- scaffolds `bricks.config.yaml`, `blueprints/`, `bricks_lib/__init__.py` in cwd; errors if config already exists
- `new brick <name>` -- generates a `BaseBrick` subclass stub in `bricks_lib/<name>.py`; normalises name (hyphens/spaces to underscores)
- `new sequence <name>` -- generates a YAML sequence template in the configured `blueprints/` dir
- `check <file>` -- loads a sequence YAML, validates against registry; exits 0 if valid, 1 with error list if not
- `run <sequence>` -- executes a sequence via `BlueprintEngine`; parses `--input key=value` pairs with JSON type coercion
- `dry-run <sequence>` -- validates a sequence via `BlueprintValidator` without executing
- `list` -- lists all registered bricks with name, tags, destructive flag, and description
- `compose <intent>` -- AI-compose stub; exits 1 with install instructions if `anthropic` is not installed

Added `_setup_registry(config_dir)` helper that loads `BricksConfig` and runs `BrickDiscovery` on configured paths when `auto_discover` is enabled.

Added 52 tests in `tests/cli/test_main.py` covering all 8 commands plus the helper, including:
- happy-path flows for each command
- error handling (missing files, invalid YAML, invalid inputs)
- auto-discovery integration
- compose stub behaviour via `unittest.mock`

### Phase 8 Details

Created four runnable examples in `examples/`:

#### `examples/yaml_blueprint.py`
Demonstrates end-to-end YAML-based sequence loading and execution:
- Defines three `@brick`-decorated functions (`multiply`, `round_value`, `format_result`)
- Registers them in a `BrickRegistry`
- Loads a `SEQUENCE_YAML` string via `BlueprintLoader.load_string()`
- Validates with `BlueprintValidator`
- Runs via `BlueprintEngine` with `inputs={"width": 7.5, "height": 4.2}`
- Asserts `area == 31.5` and `display == "Area (m²): 31.5"`

#### `examples/class_based_brick.py`
Demonstrates class-based brick definitions registered via wrapper functions:
- Defines `ReadTemperature` and `ConvertTemperature` as `BaseBrick` subclasses
- Registers thin wrapper functions (accepting keyword args) so the engine's
  `callable_(**resolved_params)` call pattern works correctly
- Builds a `BlueprintDefinition` programmatically (no YAML file)
- Runs with `inputs={"channel": 1}` and asserts `celsius == 37.0`, `fahrenheit == 98.6`

#### `examples/blueprints/power_cycle_test.yaml`
A reference YAML sequence describing a hardware power cycle test:
- Declares `device_id` and `wait_seconds` as inputs
- Five steps: `log_message`, `set_power_state` (off), `wait_seconds`, `set_power_state` (on), `check_device_online`
- Demonstrates `${inputs.device_id}` interpolation in step params and `outputs_map`

#### `examples/discovery_example.py`
Demonstrates auto-discovery of bricks from a directory:
- Creates a temp directory with `math_bricks.py` (2 bricks) and `string_bricks.py` (1 brick)
- Uses `BrickDiscovery.discover_package()` to scan and register all three bricks
- Prints schemas via `registry_schema()`
- Asserts 3 bricks discovered, verifies callable results

### Phase 7 Details

Implemented the full AI composition layer in `bricks/ai/composer.py`:

#### `ComposerError` (in `bricks/ai/composer.py`)
- Inherits from `BrickError`
- Stores optional `cause: Exception | None` for the underlying exception

#### `BlueprintComposer`
- `__init__(registry, api_key, model, max_tokens)` -- lazily imports `anthropic` inside the constructor; raises `ImportError` with install instructions if the package is missing
- `compose(intent)` -- builds a prompt from the registry schema, calls the Anthropic Messages API, extracts YAML from the response, and returns a validated `BlueprintDefinition`; wraps all failures as `ComposerError`
- `_build_bricks_context()` -- uses `registry_schema()` to generate a simplified list of brick dicts (name, description, tags, parameters) for the prompt
- `_extract_text(response)` -- extracts the text content from the first text block in an Anthropic response
- `_extract_yaml(text)` -- regex-extracts content from ` ```yaml ... ``` ` or ` ``` ... ``` ` blocks; falls back to the raw text

#### `bricks/ai/__init__.py`
Updated to export `ComposerError` and `BlueprintComposer`.

#### `pyproject.toml`
Added `ai` optional dependency group: `anthropic>=0.40`.

#### `tests/ai/test_composer.py`
17 new tests covering:
- `TestComposerInit` -- ImportError when `anthropic` not installed
- `TestComposerCompose` -- valid YAML composition, invalid YAML error, API error, no text block, empty content list
- `TestExtractYaml` -- yaml block extraction, plain code block, raw text fallback, whitespace stripping
- `TestBuildBricksContext` -- populated registry, empty registry
- `TestComposerError` -- message, no cause, BrickError inheritance, cause preservation

#### mypy --strict notes
- `import anthropic` inside `__init__` uses `# type: ignore[import-not-found]` since `anthropic` is an optional dep not installed in dev
- `_client: Any` class annotation ensures mypy accepts the dynamic Anthropic client

### Completed Phases (continued)
- [x] **Phase 9: Comprehensive Test Expansion + Integration** -- 290 tests total (up from 145)

### Phase 9 Details

Expanded test coverage across all core modules and added a new `tests/integration/` suite.

#### New/Expanded Test Files

**`tests/core/test_exceptions.py`** (expanded from 2 to 35 tests):
- Full coverage of all 8 exception classes: `BrickError`, `DuplicateBrickError`, `BrickNotFoundError`, `BlueprintValidationError`, `VariableResolutionError`, `BrickExecutionError`, `YamlLoadError`, `ConfigError`
- Tests for attribute access (`.name`, `.brick_name`, `.step_name`, `.cause`, `.path`, `.reference`, `.errors`)
- Tests for inheritance hierarchy and catchability

**`tests/core/test_brick.py`** (expanded from 3 to 24 tests):
- `TestBrickDecorator`: 10 tests covering all decorator kwargs, docstring fallback, tag lists, name propagation
- `TestBrickModel`: 4 tests covering Pydantic inheritance, type validation rejection
- `TestBaseBrick`: 6 tests covering abstract instantiation, concrete subclass, Meta defaults, execute delegation

**`tests/core/test_registry.py`** (expanded from 3 to 13 tests):
- `TestRegistryListAndHas`: 9 new tests for `list_all()` sorted order, `has()`, `clear()`, multi-brick retrieval

**`tests/core/test_context.py`** (expanded from 4 to 16 tests):
- `TestExecutionContextAdvanced`: 12 new tests for step advancement, namespace access, result priority over inputs, None inputs

**`tests/core/test_resolver.py`** (expanded from 2 to 17 tests):
- `TestResolverEdgeCases`: 15 new tests for primitives passthrough, embedded refs, multiple refs, nested dict/list, type preservation, empty collections

**`tests/core/test_engine.py`** (expanded from 1 to 10 tests):
- `TestEngineRun`: 9 new tests for literal params, inputs resolution, chained steps, error wrapping, None inputs, multiple outputs, error attribute access

**`tests/core/test_models.py`** (expanded from 3 to 20 tests):
- `TestStepDefinition`: 5 new tests for field storage
- `TestBlueprintDefinition`: 7 new tests for defaults and field setting
- `TestBrickMetaDefaults`: 7 new tests for all default values and overrides

**`tests/integration/test_full_pipeline.py`** (19 tests, NEW):
- `TestSingleStepPipeline`: 4 tests (literal params, input refs, string output, no outputs)
- `TestMultiStepPipeline`: 4 tests (chained add, multiply+round, triple chain, add+stringify)
- `TestValidationIntegration`: 4 tests (validate-then-run, missing brick, error propagation, empty registry)
- `TestDiscoveryIntegration`: 2 tests (discover_path+run, discover_package+run)
- `TestOutputsMap`: 3 tests (empty, multiple outputs, literal output value)
- `TestLoaderIntegration`: 2 tests (load_string, load_file)

**`tests/integration/test_cli_integration.py`** (12 tests, NEW):
- `TestCliEndToEnd`: 5 tests (init+brick, init+sequence, list with discovery, run real brick, check+dry-run agree)
- `TestCliRunEndToEnd`: 5 tests (add sequence, chained sequence, list multiple bricks, check valid, subtract sequence)
- `TestCliInitWorkflow`: 2 tests (full init workflow, list shows tags+description)

### Test Count History
| Phase | Tests |
|-------|-------|
| Scaffolding | 22 |
| Phase 1 (YAML Loader) | 31 |
| Phase 2 (Sub-Sequence) | 42 |
| Phase 3 (Enhanced Validation) | 63 |
| Phase 4 (Discovery + Schema) | 62 |
| Phase 5 (Configuration) | 79 |
| Phase 6 (CLI Commands) | 129 |
| Phase 8 (Examples) | 129 |
| Phase 7 (AI Composition) | 145 |
| Phase 9 (Test Expansion) | **290** |

### How to Resume
If implementation is interrupted, read this file and the plan at:
`.claude/plans/linked-crunching-whisper.md`

Then continue from the current phase marker above.
