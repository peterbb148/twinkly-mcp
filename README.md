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

## Rules of Engagement

1. **Start with an issue.** Search the [issue tracker](https://github.com/peterbb148/twinkly-mcp/issues)
   before opening a new one. Describe the problem, the outcome you want, and how
   to verify it. Agree on scope with the maintainer before starting work.
2. **Create a branch for the issue.** Start from the latest `master` and include
   the issue number in the branch name, for example `42-improve-remote-feedback`.
   If you have write access, create the branch from the issue's **Development**
   section to link it. Otherwise, create the branch in your fork and link the
   issue in the PR.
3. **Open a draft PR against `master`.** Include the issue number in the
   description, using `Closes #42` if the PR completes the issue. Describe what
   changed and how you tested it. CI runs on draft PRs. GitHub may require the
   maintainer to approve a workflow run from your fork.
4. **Mark the same PR ready for review** when the agreed work is complete and
   CI passes. Address review feedback and resolve the conversations.
5. **Merge after maintainer approval.** Changes to `master` go through a PR.
   Required CI checks must pass and [@peterbb148](https://github.com/peterbb148)
   must approve the changes as code owner before the PR can be merged.

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

When the repository is public, GitHub Actions also runs CodeQL on the Python and
JavaScript source and reviews dependency changes on pull requests.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TWINKLY_API_KEY` | Yes | API key for authentication |
| `PORT` | No | Port to bind (default: 8000) |

## Phone remote

Scan a fixed QR URL to open a static phone remote with approved presets.
See the [remote configuration and verification guide](docs/REMOTE.md).

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

## License

[MIT](LICENSE)
