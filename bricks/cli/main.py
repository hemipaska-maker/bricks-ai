"""Typer CLI application with all Bricks commands."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from bricks.core.config import BricksConfig, ConfigLoader
from bricks.core.discovery import BrickDiscovery
from bricks.core.engine import BlueprintEngine
from bricks.core.exceptions import (
    BlueprintValidationError,
    BrickExecutionError,
    YamlLoadError,
)
from bricks.core.loader import BlueprintLoader
from bricks.core.models import Verbosity
from bricks.core.registry import BrickRegistry
from bricks.core.validation import BlueprintValidator

app = typer.Typer(
    name="bricks",
    help="Bricks - Deterministic sequencing engine for typed Python building blocks.",
    no_args_is_help=True,
)

new_app = typer.Typer(help="Scaffold new Bricks components.")
app.add_typer(new_app, name="new")


def _setup_registry(
    config_dir: Path | None = None,
) -> tuple[BrickRegistry, BricksConfig]:
    """Load config and set up registry with auto-discovery.

    Args:
        config_dir: Directory to search for bricks.config.yaml. Defaults to cwd.

    Returns:
        A tuple of (registry, config).
    """
    loader = ConfigLoader()
    config = loader.load(directory=config_dir)
    registry = BrickRegistry()
    if config.registry.auto_discover:
        discovery = BrickDiscovery(registry=registry)
        for path_str in config.registry.paths:
            p = Path(path_str)
            if not p.is_absolute():
                p = (config_dir or Path.cwd()) / p
            if p.is_dir():
                discovery.discover_package(p)
            elif p.suffix == ".py" and p.exists():
                discovery.discover_path(p)
    return registry, config


@app.command()
def init() -> None:
    """Scaffold a new Bricks project in the current directory."""
    config_file = Path.cwd() / "bricks.config.yaml"
    if config_file.exists():
        typer.echo("Error: bricks.config.yaml already exists.", err=True)
        raise typer.Exit(code=1)

    config_content = """version: "1"
registry:
  auto_discover: false
  paths: []
sequences:
  base_dir: "blueprints/"
ai:
  model: "claude-haiku-4-5-20251001"
  max_tokens: 4096
"""
    config_file.write_text(config_content)
    blueprints_dir = Path.cwd() / "blueprints"
    blueprints_dir.mkdir(exist_ok=True)
    bricks_lib = Path.cwd() / "bricks_lib"
    bricks_lib.mkdir(exist_ok=True)
    (bricks_lib / "__init__.py").write_text("")
    typer.echo("Created bricks.config.yaml")
    typer.echo("Created blueprints/")
    typer.echo("Created bricks_lib/")
    typer.echo("Bricks project initialised.")


@new_app.command("brick")
def new_brick(
    name: str = typer.Argument(..., help="Name of the brick (snake_case)."),
) -> None:
    """Scaffold a new Brick module."""
    snake_name = name.lower().replace("-", "_").replace(" ", "_")
    class_name = "".join(word.capitalize() for word in snake_name.split("_"))

    output_path = Path.cwd() / "bricks_lib" / f"{snake_name}.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f'''"""Brick: {snake_name}."""

from __future__ import annotations

from bricks.core import BrickMeta, BrickModel, BaseBrick


class {class_name}(BaseBrick):
    """{class_name} brick."""

    class Meta:
        """Brick metadata."""

        name = "{snake_name}"
        tags: list[str] = []
        destructive: bool = False
        idempotent: bool = True
        description = ""

    class Input(BrickModel):
        """Input schema."""

    class Output(BrickModel):
        """Output schema."""

    def execute(self, inputs: BrickModel, metadata: BrickMeta) -> dict[str, object]:
        """Execute the brick.

        Args:
            inputs: Validated input data.
            metadata: Brick metadata.

        Returns:
            Output dict matching Output schema.
        """
        raise NotImplementedError(f"{{{class_name}}} is not yet implemented")
'''
    output_path.write_text(content)
    typer.echo(f"Created {output_path}")


@new_app.command("blueprint")
def new_blueprint(name: str = typer.Argument(..., help="Name of the blueprint.")) -> None:
    """Scaffold a new YAML blueprint file."""
    snake_name = name.lower().replace("-", "_").replace(" ", "_")

    loader = ConfigLoader()
    config = loader.load()
    bp_dir = Path.cwd() / config.sequences.base_dir
    bp_dir.mkdir(parents=True, exist_ok=True)

    output_path = bp_dir / f"{snake_name}.yaml"
    content = f"""name: {snake_name}
description: ""
inputs:
  # input_name: "type"
steps:
  - name: step_1
    brick: my_brick
    params: {{}}
    save_as: step_1_result
outputs_map:
  result: "${{step_1_result}}"
"""
    output_path.write_text(content)
    typer.echo(f"Created {output_path}")


@new_app.command("sequence")
def new_sequence(name: str = typer.Argument(..., help="Name of the sequence.")) -> None:
    """Scaffold a new YAML sequence file (alias for 'new blueprint')."""
    new_blueprint(name)


@app.command()
def check(file: str = typer.Argument(..., help="Path to blueprint YAML file.")) -> None:
    """Validate a blueprint YAML file (lint without executing)."""
    path = Path(file)
    if not path.exists():
        typer.echo(f"Error: File not found: {path}", err=True)
        raise typer.Exit(code=1)

    bp_loader = BlueprintLoader()
    try:
        blueprint = bp_loader.load_file(path)
    except YamlLoadError as exc:
        typer.echo(f"Error loading YAML: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    registry, _ = _setup_registry()
    validator = BlueprintValidator(registry=registry)

    try:
        validator.validate(blueprint)
        typer.echo(f"valid: {path}")
    except BlueprintValidationError as exc:
        typer.echo(f"Validation errors in {path}:", err=True)
        if exc.errors:
            for error in exc.errors:
                typer.echo(f"  - {error}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def run(
    sequence: str = typer.Argument(..., help="Path to blueprint YAML file."),
    input_: list[str] = typer.Option(  # noqa: B008
        [], "--input", "-i", help="Input values as key=value."
    ),
    verbosity: Verbosity = typer.Option(  # noqa: B008
        Verbosity.MINIMAL, "--verbosity", "-v", help="Output detail level (minimal/standard/full)."
    ),
) -> None:
    """Execute a blueprint."""
    path = Path(sequence)
    if not path.exists():
        typer.echo(f"Error: Blueprint file not found: {path}", err=True)
        raise typer.Exit(code=1)

    bp_loader = BlueprintLoader()
    try:
        bp_def = bp_loader.load_file(path)
    except YamlLoadError as exc:
        typer.echo(f"Error loading YAML: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    inputs: dict[str, object] = {}
    for item in input_:
        if "=" not in item:
            typer.echo(f"Error: Invalid input format {item!r}. Use key=value.", err=True)
            raise typer.Exit(code=1)
        k, v = item.split("=", 1)
        try:
            inputs[k] = json.loads(v)
        except json.JSONDecodeError:
            inputs[k] = v

    registry, _ = _setup_registry()
    engine = BlueprintEngine(registry=registry)

    try:
        exec_result = engine.run(bp_def, inputs=inputs or None, verbosity=verbosity)
    except BrickExecutionError as exc:
        typer.echo(f"Execution error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Blueprint {bp_def.name!r} completed.")
    if exec_result.outputs:
        typer.echo("Outputs:")
        for k, v in exec_result.outputs.items():
            typer.echo(f"  {k}: {v!r}")

    if verbosity in (Verbosity.STANDARD, Verbosity.FULL) and exec_result.steps:
        typer.echo("Steps:")
        for s in exec_result.steps:
            line = f"  [{s.step_name}] {s.brick_name}"
            if verbosity == Verbosity.FULL:
                line += f" ({s.duration_ms:.1f}ms)"
            typer.echo(line)
            if s.outputs:
                typer.echo(f"    outputs: {s.outputs!r}")
            if verbosity == Verbosity.FULL and s.inputs:
                typer.echo(f"    inputs:  {s.inputs!r}")

    if verbosity == Verbosity.FULL:
        typer.echo(f"Total: {exec_result.total_duration_ms:.1f}ms")


@app.command(name="dry-run")
def dry_run(
    sequence: str = typer.Argument(..., help="Path to blueprint YAML file."),
) -> None:
    """Validate a blueprint without executing (dry run)."""
    path = Path(sequence)
    if not path.exists():
        typer.echo(f"Error: Blueprint file not found: {path}", err=True)
        raise typer.Exit(code=1)

    bp_loader = BlueprintLoader()
    try:
        bp_def = bp_loader.load_file(path)
    except YamlLoadError as exc:
        typer.echo(f"Error loading YAML: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    registry, _ = _setup_registry()
    validator = BlueprintValidator(registry=registry)

    try:
        validator.validate(bp_def)
        typer.echo(f"Blueprint {bp_def.name!r} is valid (dry-run passed).")
    except BlueprintValidationError as exc:
        typer.echo("Validation errors:", err=True)
        if exc.errors:
            for error in exc.errors:
                typer.echo(f"  - {error}", err=True)
        raise typer.Exit(code=1) from exc


@app.command(name="list")
def list_bricks() -> None:
    """List all available Bricks in the registry."""
    registry, _ = _setup_registry()
    all_bricks = registry.list_all()

    if not all_bricks:
        typer.echo("No bricks registered. Check your bricks.config.yaml registry paths.")
        return

    typer.echo(f"Registered bricks ({len(all_bricks)}):")
    for name, meta in all_bricks:
        tags_str = f" [{', '.join(meta.tags)}]" if meta.tags else ""
        destructive_str = " [DESTRUCTIVE]" if meta.destructive else ""
        desc_str = f" - {meta.description}" if meta.description else ""
        typer.echo(f"  {name}{tags_str}{destructive_str}{desc_str}")


@app.command()
def compose(
    intent: str = typer.Argument(..., help="Natural language description."),
) -> None:
    """AI-compose a blueprint from a natural language description."""
    try:
        from bricks.ai.composer import BlueprintComposer  # noqa: PLC0415
    except ImportError as exc:
        typer.echo("Error: AI features require the 'anthropic' package.", err=True)
        typer.echo("Install with: pip install bricks[ai]", err=True)
        raise typer.Exit(code=1) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY") or typer.prompt("Anthropic API key", hide_input=True)
    registry, _ = _setup_registry()
    composer = BlueprintComposer(registry=registry, api_key=api_key)

    try:
        result_blueprint = composer.compose(intent)
        typer.echo(f"Composed blueprint: {result_blueprint.name!r}")
        typer.echo(f"  Steps: {len(result_blueprint.steps)}")
    except NotImplementedError as exc:
        typer.echo("AI composition is not yet fully implemented.", err=True)
        raise typer.Exit(code=1) from exc
