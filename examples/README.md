# Bricks Examples

**Start here** → [end_to_end/quickstart.py](end_to_end/quickstart.py) — see Bricks in action in 30 seconds
**Learn each piece** → [basics/01_hello_brick.py](basics/01_hello_brick.py) — understand how each building block works

Bricks is a deterministic execution engine. You describe a task in natural language; Bricks composes a YAML blueprint once (via LLM), then executes it deterministically every time — zero tokens on repeat runs.

---

## End-to-end (hero)

Run these first. They show real data pipelines with real outputs.

| Example | What it shows |
|---------|--------------|
| [end_to_end/quickstart.py](end_to_end/quickstart.py) | 5 CRM records → filter active → count. 30-second demo. |
| [end_to_end/crm_pipeline.py](end_to_end/crm_pipeline.py) | 50-record CRM dataset → filter, count, verify against expected outputs |
| [end_to_end/ticket_pipeline.py](end_to_end/ticket_pipeline.py) | 100 support tickets → validate emails, filter by priority, count |
| [end_to_end/langchain_tool.py](end_to_end/langchain_tool.py) | Wrap `engine.execute()` as a LangChain (or any framework) tool |
| [end_to_end/mcp_server/](end_to_end/mcp_server/) | Expose Bricks as an MCP server for Claude Desktop |

All end-to-end examples run in **demo mode** (no API key) with a pre-composed blueprint, or in **live mode** with your API key:

```bash
# Demo mode (no API key)
python examples/end_to_end/quickstart.py

# Live mode — set your key and optionally the model
ANTHROPIC_API_KEY=sk-ant-... python examples/end_to_end/quickstart.py
BRICKS_MODEL=gpt-4o-mini OPENAI_API_KEY=sk-... python examples/end_to_end/quickstart.py
```

---

## Basics

One concept per file. All run standalone with no API key.

| Example | Concept |
|---------|---------|
| [basics/01_hello_brick.py](basics/01_hello_brick.py) | Define `@brick`, register, run a blueprint |
| [basics/02_class_based_brick.py](basics/02_class_based_brick.py) | `BaseBrick` with typed `Input`/`Output` schemas |
| [basics/03_yaml_blueprint.py](basics/03_yaml_blueprint.py) | Load blueprint from YAML string → validate → execute |
| [basics/04_nested_blueprints.py](basics/04_nested_blueprints.py) | Parent blueprint calling a child blueprint as a step |
| [basics/05_discovery.py](basics/05_discovery.py) | Auto-discover bricks from a directory with `BrickDiscovery` |
| [basics/06_skill_config.py](basics/06_skill_config.py) | Boot from `agent.yaml` or `skill.md` config files |

```bash
python examples/basics/01_hello_brick.py
python examples/basics/02_class_based_brick.py
# ... and so on
```

---

## Config

| File | Purpose |
|------|---------|
| [config/agent.yaml](config/agent.yaml) | Full agent config: model, store backend, selector, skills |
| [config/skill.md](config/skill.md) | Example skill description for `Bricks.from_skill()` |
