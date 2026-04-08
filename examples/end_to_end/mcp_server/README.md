# Bricks as an MCP Server

Expose the Bricks engine to Claude Desktop (or any MCP-compatible client) with tools, resources, and prompt templates.

## Installation

```bash
pip install "bricks-ai[ai,mcp]"
```

## Configuration (Claude Desktop)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bricks": {
      "command": "bricks",
      "args": ["serve"],
      "env": { "ANTHROPIC_API_KEY": "your-key-here" }
    }
  }
}
```

See [mcp_config.json](mcp_config.json) for a ready-to-copy snippet.

## What the Server Exposes

### Tool: `execute_task`

| Field     | Type   | Required | Description                                      |
|-----------|--------|----------|--------------------------------------------------|
| `task`    | string | yes      | Natural language description of what to compute. |
| `inputs`  | object | no       | Input values for `${inputs.key_name}` references.|
| `verbose` | bool   | no       | If true, returns step-by-step execution trace.   |

Example call:

```json
{
  "task": "filter active users and compute total spend",
  "inputs": {
    "users": [
      {"id": 1, "active": true, "spend": 42.0},
      {"id": 2, "active": false, "spend": 10.0}
    ]
  },
  "verbose": true
}
```

Example response:

```json
{
  "outputs": {"total_spend": 42.0, "active_count": 1},
  "cache_hit": false,
  "api_calls": 1,
  "input_tokens": 245,
  "output_tokens": 67
}
```

On subsequent calls with the same task description the blueprint is served from the store: `cache_hit` is `true` and tokens are `0`.

### Resources

| URI | Description |
|-----|-------------|
| `bricks://catalog` | All available bricks with name, description, and category |
| `bricks://blueprints` | All cached blueprints in the store |

### Prompt Templates

The server includes built-in prompt templates for common tasks, accessible via the MCP prompts protocol.

### Blueprint Persistence

Blueprints cache to `~/.bricks/blueprints` by default (file-based store). Cache survives server restarts — no recomposition needed for previously seen tasks.

## Advanced

```bash
# Use a custom config file
bricks serve --config examples/config/agent.yaml

# Use a different model
bricks serve --model gpt-4o-mini
```
