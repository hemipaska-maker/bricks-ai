"""bricks_ai — the AI layer for Bricks.

Everything that talks to an LLM lives here: blueprint composition, healing,
provider adapters, the natural-language task orchestrator, and the playground.
Execution stays in the deterministic ``bricks`` engine — this package imports
``bricks``, never the other way around.
"""

from bricks_ai.api import Bricks
from bricks_ai.composer import BlueprintComposer, CallDetail, ComposerError, ComposeResult
from bricks_ai.orchestrator import RuntimeOrchestrator

# Deprecated alias — will be removed in v1.0.0
SequenceComposer = BlueprintComposer

__version__ = "1.0.0"

__all__ = [
    "BlueprintComposer",
    "Bricks",
    "CallDetail",
    "ComposeResult",
    "ComposerError",
    "RuntimeOrchestrator",
    "SequenceComposer",
    "__version__",
]
