# Bricks Playground — Build Spec (v1, local-only)

**Status:** approved for build
**Target:** ships as part of v0.5.0 milestone
**Prerequisite:** repo on main, post-Phase-1 layout (`src/bricks/` single package)

---

## 1. Context

Transform the existing `bricks.playground.web` module into `bricks.playground` — a local web UI that lets users try Bricks against embedded scenarios with live LLM execution. Replaces the CLI benchmark as the primary "try it" experience.

**One-liner UX target:**

```bash
$ pip install bricks
$ bricks playground
✓ Bricks Playground running → http://localhost:8080
  (browser opened · Ctrl+C to stop)
```

Local-only in v1. No hosted deployment, no auth, no persistence beyond the session.

---

## 2. Scope

**In:**
- Full rename `bricks.playground` → `bricks.playground` (module, tests, docs, CLI, URLs)
- New UI from v2 mockup (see §9)
- Four provider adapters: Anthropic, OpenAI, Claude Code (local CLI), Ollama (localhost)
- BYOK flow — key in request body, never env var
- File upload (CSV/JSON)
- "Compare to raw LLM" toggle (OFF by default)
- One-liner CLI: `bricks playground`
- Browser auto-open
- Bundled web deps in default `pip install bricks`

**Out (defer to later):**
- Hosted deployment
- Share-by-URL (the Share button is UI-only in v1)
- Run history / persistence
- Multi-user auth
- Pricing / usage metering

---

## 3. File / module rename

Rename across the codebase:

| From | To |
|---|---|
| `src/bricks/benchmark/` | `src/bricks/playground/` |
| `tests/benchmark/` | `tests/playground/` |
| `bricks.playground.*` imports | `bricks.playground.*` |
| Web route prefix `/benchmark` | `/playground` |
| CLI subcommand `bricks benchmark` | `bricks playground` |
| AGENTS.md references | update |
| README example commands | update |
| CHANGELOG entry | add under v0.5.0 |

Do this in one commit. Keep git history clean with `git mv`.

---

## 4. CLI entry point

Add to `pyproject.toml`:

```toml
[project.scripts]
bricks = "bricks.cli:main"
```

Extend (or create) `src/bricks/cli.py` with a `playground` subcommand:

```
bricks playground [--port N] [--host HOST] [--no-browser]
```

**Default behavior:**
- Pick free port (prefer 8080, fall back if taken)
- Bind `127.0.0.1` (local-only)
- Start uvicorn serving the FastAPI app
- Open `webbrowser.open(url)` after 0.3s delay
- Print: `✓ Bricks Playground running → http://localhost:PORT`
- Print: `(browser opened · Ctrl+C to stop)`
- Graceful Ctrl+C → clean shutdown, no traceback

**Flags:**
- `--port N` — force specific port, fail if taken
- `--host HOST` — bind to different host (e.g. `0.0.0.0` for LAN)
- `--no-browser` — skip auto-open (for headless/remote users)

---

## 5. Frontend

**Source of truth:** `Documents/Claude/Projects/Bricks/playground_mockup_v2.html` (reference copy in Cowork folder).

**Copy to:** `src/bricks/playground/web/static/index.html`

**Cleanup during copy:**
- Strip unused font imports: Fraunces, Space Grotesk, Playfair Display
- Keep only: Inter, Instrument Serif, JetBrains Mono

**Wire hardcoded JS to real endpoints:**

| Mockup hardcoded | Replace with |
|---|---|
| `const customers = {...}` | Fetch from `GET /playground/scenarios/{name}` |
| Scenario dropdown options | Fetch from `GET /playground/scenarios` |
| Run button mock flow | `POST /playground/run` with config |
| Results page mock data | Render from `/run` response |
| File upload button (static) | `POST /playground/upload` with file, replace data-body preview |

**Frontend state management:** vanilla JS (no framework). Keep it single-file, match the existing style.

**Provider → key field visibility:**

| Provider selected | API key field |
|---|---|
| Anthropic | visible, required |
| OpenAI | visible, required |
| Claude Code | hidden, replaced with "authenticated via local CLI" label |
| Ollama / Llama3 local | hidden, replaced with "localhost:11434" label |

**Model dropdown options per provider:**

| Provider | Models shown |
|---|---|
| Anthropic | Haiku 4.5, Sonnet 4.5, Opus 4.5 |
| OpenAI | GPT-4o Mini, GPT-4o |
| Claude Code | (inherit from local CLI's model) — single "Claude Code" option |
| Ollama | Llama3, Mistral, plus anything from `ollama list` (if possible) |

---

## 6. Backend endpoints

FastAPI app at `src/bricks/playground/web/app.py`. All routes under `/playground` prefix.

### `GET /playground/scenarios`

Returns list of available preset scenarios.

```json
[
  {"id": "crm-pipeline", "name": "CRM · customer aggregates", "description": "Filter + aggregate active customers"},
  {"id": "crm-hallucination", "name": "CRM · consistency at scale", "description": "..."},
  ...
]
```

Loads from `src/bricks/playground/web/presets/` (existing folder).

### `GET /playground/scenarios/{id}`

Returns a full scenario:

```json
{
  "id": "crm-pipeline",
  "task": "Parse the customer JSON...",
  "data": { ... },
  "expected_output": {"active_count": 18, ...}
}
```

### `POST /playground/upload`

Accepts CSV or JSON file. Returns:

```json
{"data": {...}, "filename": "customers.json", "size_bytes": 3200, "row_count": 24}
```

Server-side: parse CSV → list of dicts; JSON → load as-is. Reject anything >5 MB.

### `POST /playground/run`

Request body:

```json
{
  "provider": "anthropic" | "openai" | "claude_code" | "ollama",
  "model": "claude-haiku-4-5",
  "api_key": "sk-...",         // required for anthropic/openai, absent for others
  "task": "Parse the customer JSON...",
  "data": {...},
  "expected_output": {...},     // optional
  "compare": false              // default false
}
```

Response:

```json
{
  "bricks": {
    "blueprint_yaml": "...",
    "bricks_used": [{"name": "filter_dict_list", "category": "list", "count": 1}, ...],
    "outputs": {"active_count": 18, ...},
    "tokens": {"in": 1800, "out": 600, "total": 2400},
    "duration_ms": 6200,
    "cost_usd": 0.0012,
    "checks": [{"key": "active_count", "expected": 18, "got": 18, "pass": true}, ...]
  },
  "raw_llm": {                  // only if compare=true
    "response": "...",
    "outputs": {...},
    "tokens": {...},
    "duration_ms": 4900,
    "cost_usd": 0.0049,
    "checks": [...]
  },
  "run_metadata": {
    "model": "claude-haiku-4-5",
    "seed": 42,
    "version": "0.5.0",
    "timestamp": "2026-04-20T..."
  }
}
```

**Compare toggle behavior:** when `compare=false`, skip RawLLMEngine call entirely. Do not pre-compute, do not cache. Response omits the `raw_llm` key.

---

## 7. Provider adapters

New file: `src/bricks/playground/providers.py`

Abstract base:

```python
class Provider(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, model: str, **kwargs) -> ProviderResponse: ...
```

Four implementations:

**`AnthropicProvider`**
- Uses `anthropic` SDK (existing dep)
- API key from request body → passed to SDK client
- Never stored server-side

**`OpenAIProvider`**
- Uses `openai` SDK (add to deps)
- API key from request body

**`ClaudeCodeProvider`**
- Shells out to local `claude` CLI via `subprocess.run(["claude", "--print", prompt])`
- No key handling (CLI handles auth)
- Check for `claude` on PATH at server start; return clear error if missing
- This provider ONLY works when server is running on user's machine (which is always, per local-only v1)

**`OllamaProvider`**
- HTTP POST to `http://localhost:11434/api/generate`
- Check `GET /api/tags` at server start to list available models
- Fail gracefully with helpful error if Ollama isn't running

All four return a unified `ProviderResponse` with `text`, `tokens_in`, `tokens_out`, `duration_ms`, `cost_usd` (cost=None for local providers).

---

## 8. Install / packaging

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    # existing deps...
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "python-multipart",  # for file upload
    "openai>=1.0",       # new, for OpenAI provider
    "httpx",             # for Ollama HTTP calls
]
```

`pip install bricks` gives everything needed to run `bricks playground`. No extras required.

---

## 9. Reference artifacts

- **UI mockup:** `Documents/Claude/Projects/Bricks/playground_mockup_v2.html`
  - Read this for layout, copy, and interaction patterns
  - Font stripping + wiring happens during copy to static/index.html
- **Existing backend:** `src/bricks/benchmark/web/` (becomes `src/bricks/playground/web/`)
  - `app.py`, `routes.py`, `scenario_loader.py`, `datasets/`, `presets/`, `ticket_generator.py`
  - Reuse the scenario/dataset loading logic, rewrite the route layer

---

## 10. Tests

`tests/playground/`:

- **`test_cli.py`** — `bricks playground --no-browser --port 0` starts, serves index, shuts down
- **`test_endpoints.py`** — each endpoint happy path + one failure
- **`test_providers.py`** — mocked Anthropic, OpenAI, Claude Code (subprocess mock), Ollama (httpx mock)
- **`test_compare.py`** — compare=false skips raw_llm call (assert no LLM invocation for raw path)
- **`test_upload.py`** — CSV and JSON upload, oversize rejection

CI matrix already covers 3.10/3.11/3.12 — no changes needed.

---

## 11. Acceptance criteria

- [ ] `pip install -e .` then `bricks playground` → browser opens, Playground UI loads
- [ ] All four providers work (manual smoke with real keys + local Claude Code + local Ollama)
- [ ] Compare toggle OFF → no raw LLM call in server logs; results page shows only Bricks column
- [ ] Compare toggle ON → both engines run, comparison table has both columns
- [ ] CSV upload with 100 rows renders correctly, executes correctly
- [ ] Ctrl+C shuts down cleanly, no zombie process
- [ ] All references to "benchmark" replaced with "playground" (grep returns clean)
- [ ] CI green on 3.10/3.11/3.12
- [ ] README updated with `bricks playground` as the primary onboarding flow

---

## 12. Suggested GitHub Issue breakdown

Split into focused PRs:

1. **Rename + CLI entry point** (mechanical, easy review)
2. **Frontend drop-in** (HTML/JS only, no backend changes yet — uses mock data)
3. **Backend endpoints** (GET scenarios, POST run, POST upload)
4. **Provider adapters** (Anthropic + OpenAI first, then Claude Code + Ollama)
5. **Compare toggle wiring + tests**
6. **README + AGENTS.md update, polish, acceptance-criteria pass**

Each PR independently reviewable and shippable. Milestone: v0.5.0.
