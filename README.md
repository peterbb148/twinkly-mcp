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
# Install the committed dependency versions, including development tools
uv sync --locked

# Run locally
uv run --locked uvicorn twinkly_mcp.server:app --reload

# Run tests
uv run --locked pytest --cov=twinkly_mcp --cov-branch --cov-report=term-missing --cov-fail-under=81
uv run --locked ruff check src/ tests/
uv run --locked ruff format --check src/ tests/
```

Python 3.11 is selected by `.python-version`. Use UV for dependency changes:
`uv add PACKAGE`, `uv add --dev PACKAGE`, and `uv remove PACKAGE`. Commit both
`pyproject.toml` and `uv.lock`. To refresh versions within the declared constraints,
run `uv lock --upgrade`, then run the checks above.

To audit the locked production and development dependencies:

```bash
uv export --locked --all-groups --no-emit-project --format requirements-txt --output-file /tmp/twinkly-mcp-audit.txt
uv run --locked pip-audit --no-deps --disable-pip --requirement /tmp/twinkly-mcp-audit.txt
```

CI runs these checks on pull requests and pushes to `master`, and weekly to catch
new advisories. Dependabot checks UV dependencies and GitHub Actions weekly.
GitHub Dependabot alerts and security updates must also be enabled in repository
settings; adding the configuration does not enable those settings.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TWINKLY_API_KEY` | Yes | API key for authentication |
| `PORT` | No | Port to bind (default: 8000) |

## Deployment

The Render blueprint is `render.yaml`; the repository's default branch is `master`.
Render auto-deployment follows the branch configured for the service.

Render detects the committed `uv.lock` and provides UV natively. The blueprint
pins UV 0.13.1 and Python 3.11.17, installs production dependencies with
`uv sync --locked --no-dev`, and starts Uvicorn with `uv run --locked --no-sync`.
The lockfile is the single dependency source for development, CI, and deployment;
there is no separate `requirements.txt`.

Existing Render services must have the blueprint changes applied (or the build,
start, and version settings updated in the dashboard). Merging this file alone
does not verify the settings of an existing service. After deploying, verify
`/health` and an authenticated MCP tool call followed by Raspberry Pi polling.
