# Twinkly MCP

MCP server for remote control of a Twinkly LED wall. Deployed on Render, controlled via Claude Desktop or other MCP clients.

## Architecture

```
Claude Desktop ──MCP──▶ Render (twinkly-mcp) ◀──HTTP poll── Raspberry Pi
```

## MCP Tools

- `twinklysay(text)` - Display a text message on the LED wall
- `run_card(card_id)` - Run a specific display card (clock, pacman, snow, etc.)

## HTTP API (for Raspberry Pi)

- `GET /api/commands/poll?after=<last_id>` - Poll for new commands
- `GET /health` - Health check

## Development

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn twinkly_mcp.server:app --reload

# Run tests
uv run pytest
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TWINKLY_API_KEY` | Yes | API key for authentication |
| `PORT` | No | Port to bind (default: 8000) |

## Deployment

Deployed to Render via `render.yaml`. Auto-deploys from main branch.
