---
name: twinkly-mcp
description: Use the Twinkly MCP server to list available LED wall cards, display a message, or run a display card.
---

# Twinkly MCP

## Connect

Use a Streamable HTTP MCP client with `https://twinkly-mcp.onrender.com/mcp`.
Supply `TWINKLY_API_KEY` as a bearer token through the client's secret mechanism.
Keep the key out of prompts, logs, and tracked configuration.

For Codex, provide `TWINKLY_API_KEY` in the environment of the Codex process,
then register the server and start a new session if needed.

```bash
codex mcp add twinkly --url https://twinkly-mcp.onrender.com/mcp \
  --bearer-token-env-var TWINKLY_API_KEY
```

For Claude Desktop setup, see [issue #3](https://github.com/peterbb148/twinkly-mcp/issues/3).

## Use the wall

- **“What cards are available?”** Call `list_cards()` and report the returned
  IDs. Use this read-only call after initialization to verify the connection.
- **“Run the clock card.”** Call `list_cards()` to resolve the requested card
  to a current ID, then call `run_card` with `{"card_id": "clock"}` if `clock`
  is available. If the server reports an unknown card, refresh the list and
  show the user the available choices.
- **“Show ‘Welcome!’ in green.”** Call `twinklysay` with
  `{"text": "Welcome!", "color": "green"}`. Text must be nonblank and at most
  200 characters. Omit `color` unless requested. The tool accepts a color name
  or a hex code such as `#00FF00`.

Send `run_card` or `twinklysay` only when the user requests a display change.
If a call returns `status: queued`, report the command ID and say that playback
is unverified unless someone has confirmed it on the wall. If the call times
out after submission, report the uncertain outcome before attempting another
display command.

If the key is missing or the server returns HTTP `401`, check that the client
process can read `TWINKLY_API_KEY` and that the configured key is current. Report
the authentication failure without exposing the key.
