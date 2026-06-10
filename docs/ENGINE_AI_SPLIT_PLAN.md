# Engine / AI Split Plan

> **Status: IMPLEMENTED** (branch `refactor/engine-ai-split`; the `pre-decoupling`
> git tag marks the last coupled commit). The implementation went one step further
> than §2 below: the AI layer moved to its own **top-level package `src/bricks_ai/`**
> (not `bricks.ai`), so a future GitHub/PyPI split is mechanical — each repo takes
> one source directory plus a pyproject. Layout as built:
>
> - `src/bricks/` — engine: `core`, `stdlib`, `store`, `selector`, `boot` (YAML-only),
>   `packs`, `cli`, `api.py` (`build_default_registry`, `run_blueprint`)
> - `src/bricks_ai/` — AI: `composer`, `healing`, `orchestrator`, `skill_boot`,
>   `api.py` (the `Bricks` facade), `llm/` (+ shared provider `factory`),
>   `providers/`, `mcp/`, `playground/`, `demo/`, `skills/`
> - Enforcement: import-linter contract (pyproject), `tests/core/test_no_ai_imports.py`,
>   and the `engine-only` CI job (base install, no LLM SDKs, engine test suites).
> - `from bricks import Bricks` now raises an ImportError pointing to
>   `from bricks_ai import Bricks`.

**Goal:** make the brick engine a standalone, deterministic code tool with zero LLM involvement —
`pip install bricks-ai` (no extras) and `import bricks` must give you a pure engine that never
imports, depends on, or calls any AI code. Everything LLM-related (composer, healing, providers,
skill extraction, orchestration of natural-language tasks) lives in a clearly separated AI layer
that *uses* the engine, never the other way around.

---

## 1. Current state (verified)

### Already clean — zero AI/LLM imports
| Module | Role |
|---|---|
| `src/bricks/core/` | Engine: `@brick`, registry, DSL tracer, DAG, `BlueprintEngine.run()`, validators, loader, resolver |
| `src/bricks/stdlib/` | ~95 pure deterministic bricks (incl. new `data_ops.py`) |
| `src/bricks/store/` | Blueprint cache (file/memory) — pure persistence |
| `src/bricks/selector/` | Keyword tier (deterministic); embedding tier uses an injected `EmbeddingProvider` ABC, no SDK imports |

### Leak points — engine side importing AI
| File | Leak |
|---|---|
| `src/bricks/__init__.py:3` | `from bricks.api import Bricks` → transitively imports the whole AI layer on `import bricks` |
| `src/bricks/api.py` | `Bricks` facade imports `RuntimeOrchestrator` eagerly; `default()` builds `LiteLLMProvider` |
| `src/bricks/orchestrator/runtime.py:11,19,87` | Hard imports of `bricks.ai.composer`, `bricks.llm.base`, `LiteLLMProvider` |
| `src/bricks/boot/bootstrapper.py:18,157` | `LLMProvider` type + LLM call for `skill.md` extraction |
| `src/bricks/cli/main.py:412-464` | `compose`/`demo` commands import AI (already lazy — just needs friendly gating) |
| `src/bricks/playground/provider_factory.py` | The *shared* provider factory lives under playground — wrong home |

Dependencies in `pyproject.toml` are already split correctly: base = pydantic/typer/ruamel/rich,
LLM SDKs only in `ai` / `playground` extras. The problem is **code-level coupling**, not deps.

---

## 2. Target architecture

```
ENGINE (deterministic, importable with zero AI code loaded)
  bricks.core, bricks.stdlib, bricks.store, bricks.selector,
  bricks.boot (YAML only), bricks.packs, engine CLI commands
  Public seam: BrickRegistry · BlueprintLoader · BlueprintValidator · BlueprintEngine.run()

        ▲  (AI imports engine — never the reverse)

AI LAYER (optional extra, all LLM concerns)
  bricks.ai        composer, healing, RuntimeOrchestrator, skill extraction, AI facade
  bricks.llm       LLMProvider ABC, LiteLLMProvider, provider factory
  bricks.providers anthropic / openai / ollama / claudecode
  bricks.mcp, bricks.playground, bricks.demo
```

Import rule (mechanically enforced, see §3.7): `bricks.{core,stdlib,store,selector,boot,packs}`
and the top-level `bricks/__init__.py` may never import
`bricks.{ai,llm,providers,mcp,playground,demo}`.

---

## 3. Phase 1 — decouple in-repo (the actual work)

### 3.1 Move `RuntimeOrchestrator` into the AI layer
- `src/bricks/orchestrator/runtime.py` → `src/bricks/ai/orchestrator.py` (with `_build_selector` /
  `_build_store` helpers). Its whole job is compose→execute, which is inherently AI.
- `src/bricks/orchestrator/input_mapper.py` → `src/bricks/core/input_mapper.py` (pure deterministic,
  useful engine-side).
- Delete `src/bricks/orchestrator/` (project is 0.5.0-dev alpha; no shim needed). Update importers:
  `api.py`, tests under `tests/orchestrator/`.

### 3.2 Split the public facade (`api.py`)
- **Engine facade** stays in `src/bricks/api.py` (or `engine_api.py`): keep `_build_default_registry()`,
  add a deterministic `run_blueprint(path_or_yaml, inputs, registry=None)` helper wrapping
  `BlueprintLoader` + `BlueprintValidator` + `BlueprintEngine.run()`. No LLM symbols anywhere.
- **AI facade** — move class `Bricks` (`from_config` / `from_skill` / `default` / `execute`) to
  `src/bricks/ai/api.py`, re-export from `bricks.ai.__init__`.
- **Back-compat:** in `src/bricks/__init__.py` add a PEP 562 module `__getattr__` that resolves
  `Bricks` via `importlib.import_module("bricks.ai.api")` on first access. `from bricks import Bricks`
  keeps working for AI users; plain `import bricks` loads zero AI modules. (Use `importlib` with a
  string, not an `import` statement, so the import-linter contract stays clean.)

### 3.3 Split the bootstrapper (`boot/bootstrapper.py`)
- Engine-side `SystemBootstrapper` keeps only the `agent.yaml` path. Remove
  `from bricks.llm.base import LLMProvider`, `_from_markdown`, `_extract_from_llm`.
  `.md` input → raise `ValueError` pointing to the AI layer.
- Move markdown skill extraction to `src/bricks/ai/skill_boot.py` (`_EXTRACT_SYSTEM` prompt,
  `_extract_from_llm`, `_extract_md_title`). `Bricks.from_skill()` (now AI-side) calls it directly
  and builds the `SystemConfig` itself.

### 3.4 Relocate the provider factory
- `src/bricks/playground/provider_factory.py` → `src/bricks/llm/factory.py`
  (`build_provider`, `infer_provider`, `resolve_api_key`, `SUPPORTED_PROVIDERS`). It is the shared
  factory for CLI, playground web, and demo — it does not belong under playground.
- Update importers: `playground/web/routes.py`, playground CLI run path, `cli/main.py` (demo),
  `playground/web/schemas.py` (Literal over `SUPPORTED_PROVIDERS`).

### 3.5 CLI: one binary, gated AI commands
- Engine commands unchanged: `init`, `new`, `check`, `run`, `dry-run`, `list`, `check-env`, `store`.
- `compose` and `demo`: keep lazy imports, wrap in `try/except ImportError` with a friendly message:
  `"AI commands require the AI extra: pip install bricks-ai[ai]"`. (Today the failure surfaces as a
  raw litellm ImportError at provider construction.)

### 3.6 Packaging metadata
- Keep a **single distribution** in Phase 1. Base install is already engine-only by dependencies;
  after 3.1–3.3 it is engine-only by imports too.
- Optional polish: add `anthropic` / `openai` extras for the direct SDK providers (currently only
  reachable via the `playground` extra).

### 3.7 Enforce the boundary (so it never regresses)
- Add **import-linter** to dev deps with a "forbidden" contract:
  source `bricks.core | bricks.stdlib | bricks.store | bricks.selector | bricks.boot | bricks.packs | bricks (root) | bricks.api`
  forbidden `bricks.ai | bricks.llm | bricks.providers | bricks.mcp | bricks.playground | bricks.demo`.
  `bricks.cli` is excluded (its AI imports are intentionally lazy + gated).
- Add a guard test `tests/core/test_no_ai_imports.py`: import `bricks`, assert no module in
  `sys.modules` starts with `bricks.ai` / `bricks.llm` / `bricks.providers`.
- Add a CI job **engine-only** in `.github/workflows/ci.yml`: `pip install .` with *no extras*
  (+ pytest), then run `pytest tests/core tests/stdlib tests/store tests/selector tests/boot`
  and `python -c "import bricks"`. This proves the engine works in an environment where litellm /
  anthropic / openai are not even installed.
- Run `lint-imports` in the existing lint job.

### 3.8 Tests
- Move `tests/orchestrator/` → `tests/ai/` (they mock the provider already).
- Move markdown-bootstrap tests from `tests/boot/` to `tests/ai/`.
- Everything else stays; the conftest `llm_provider` fixture and `--live` marker are unchanged.

### 3.9 Docs
- README: update the architecture section — two install stories
  (`pip install bricks-ai` = deterministic engine; `pip install bricks-ai[ai]` = + composer),
  state the import rule. Re-run cog (README has auto-generated sections).
- AGENTS.md: document the layer rule so future work respects it.

---

## 4. Phase 2 (optional, later) — separate distributions
Once the boundary has been stable for a while, the AI layer can be physically extracted:
`bricks-engine` wheel (core/stdlib/store/selector/boot/cli) + `bricks-ai` wheel depending on it.
Requires: two pyprojects (workspace or repo split), entry-point coordination for the shared `bricks`
CLI, release/version coordination, CI matrix. **Not recommended yet** — Phase 1 delivers the actual
guarantee (engine importable and testable with zero AI) at a fraction of the maintenance cost, and
Phase 2 becomes mechanical once the import boundary is enforced.

---

## 5. Sequencing
1. Land the in-flight stdlib `data_ops` work first (engine-side, no conflict with this plan).
2. PR A — the decoupling: §3.1 orchestrator move, §3.2 facade split, §3.3 bootstrapper split.
3. PR B — §3.4 provider factory move, §3.5 CLI gating.
4. PR C — §3.7 enforcement (import-linter, guard test, engine-only CI job), §3.8 test moves.
5. PR D — §3.9 docs + §3.6 packaging polish.

## 6. Verification
- Full suite: `.venv/Scripts/python.exe -m pytest` — green (mocked providers, `--live` excluded by default).
- Boundary proof in a **fresh venv with no extras**:
  `pip install .` → `python -c "import bricks; print(bricks.__version__)"` succeeds,
  `pip list` shows no litellm/anthropic/openai, `bricks run <example blueprint>` works,
  `bricks compose "x"` prints the friendly install hint instead of a traceback.
- `lint-imports`, `ruff check`, `mypy src/bricks` (strict), cog — all via the venv python.
- CI green on the PR, including the new engine-only job.
