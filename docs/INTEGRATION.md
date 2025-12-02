# Twinkly MCP Server Integration Guide

This document describes how to integrate with the Twinkly MCP server from the Raspberry Pi running twinkly-wall.

## Server URL

**Production:** `https://twinkly-mcp.onrender.com`

## Architecture Overview

```
┌─────────────────┐     MCP Protocol      ┌──────────────────┐
│  Claude Desktop │ ◄──────────────────► │  Twinkly MCP     │
│  (MCP Client)   │                       │  Server (Render) │
└─────────────────┘                       └────────┬─────────┘
                                                   │
                                          HTTP Polling
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Raspberry Pi    │
                                          │  (twinkly-wall)  │
                                          └──────────────────┘
```

Claude Desktop sends commands via MCP protocol. The Pi polls the server for new commands via HTTP.

## HTTP API Endpoints

### Health Check

```
GET /health
```

Response:
```json
{"status": "healthy", "service": "twinkly-mcp"}
```

### Poll for Commands

```
GET /api/commands/poll
GET /api/commands/poll?after=<last_command_id>
```

The `after` parameter allows incremental polling - only commands newer than the specified ID are returned.

**Response:**
```json
{
  "commands": [
    {
      "id": "cmd_000001",
      "type": "twinklysay",
      "payload": {"text": "Hello World"},
      "created_at": "2025-12-02T17:30:00.123456"
    },
    {
      "id": "cmd_000002",
      "type": "run_card",
      "payload": {"card_id": "clock"},
      "created_at": "2025-12-02T17:30:05.654321"
    }
  ]
}
```

## Command Types

### 1. twinklysay

Display scrolling text on the LED wall.

```json
{
  "id": "cmd_000001",
  "type": "twinklysay",
  "payload": {
    "text": "Message to display (max 200 chars)"
  },
  "created_at": "2025-12-02T17:30:00.123456"
}
```

### 2. run_card

Switch to a specific display card/animation.

```json
{
  "id": "cmd_000002",
  "type": "run_card",
  "payload": {
    "card_id": "clock"
  },
  "created_at": "2025-12-02T17:30:05.654321"
}
```

**Available card IDs:**
- `beer`, `calendar`, `carlsberg_lab`, `clock`, `coffee`
- `confetti`, `countdown`, `fire`, `fireworks`, `friday`
- `image`, `lava`, `leaderboard`, `matrix`, `menorah`
- `news`, `ocean`, `pacman`, `pacman_chase`, `pong`
- `pomodoro`, `quote`, `rainbow`, `santa`, `snake`
- `snow`, `space_invaders`, `starfield`, `test_pattern`
- `tetris`, `text`, `tuborg_julebryg`, `twinklysay`, `weather`

Note: The card list is dynamic. The Raspberry Pi can register its available cards on startup (see Card Registration below).

## Polling Implementation

### Recommended Polling Logic

```python
import requests
import time

SERVER_URL = "https://twinkly-mcp.onrender.com"
POLL_INTERVAL = 2  # seconds

def poll_commands(last_id: str | None = None) -> tuple[list, str | None]:
    """Poll for new commands.

    Returns:
        Tuple of (commands list, new last_id)
    """
    url = f"{SERVER_URL}/api/commands/poll"
    if last_id:
        url += f"?after={last_id}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    commands = data.get("commands", [])

    # Track the last command ID for next poll
    new_last_id = commands[-1]["id"] if commands else last_id

    return commands, new_last_id

def process_command(cmd: dict):
    """Process a single command."""
    cmd_type = cmd["type"]
    payload = cmd["payload"]

    if cmd_type == "twinklysay":
        # Display the text message
        display_text(payload["text"])
    elif cmd_type == "run_card":
        # Switch to the specified card
        switch_to_card(payload["card_id"])

# Main polling loop
last_id = None
while True:
    try:
        commands, last_id = poll_commands(last_id)
        for cmd in commands:
            process_command(cmd)
    except requests.RequestException as e:
        print(f"Polling error: {e}")

    time.sleep(POLL_INTERVAL)
```

### Key Points

1. **Use `after` parameter**: Always pass the last seen command ID to avoid reprocessing commands
2. **Handle network errors**: The server may be temporarily unavailable
3. **Poll interval**: 2-5 seconds is reasonable for responsive UX without excessive requests
4. **Command ordering**: Commands are returned in chronological order
5. **Queue size**: Server keeps last 100 commands in memory

## Authentication (Optional)

If `TWINKLY_API_KEY` is set on the server, requests must include:

```
Authorization: Bearer <api_key>
```

Example:
```python
headers = {"Authorization": f"Bearer {api_key}"}
response = requests.get(url, headers=headers, timeout=10)
```

The `/health` endpoint does not require authentication.

## Error Responses

### 401 Unauthorized
```json
{"error": "Authentication required. Provide Authorization: Bearer <token>"}
```
or
```json
{"error": "Invalid API key"}
```

## Testing

Test the connection:
```bash
# Health check
curl https://twinkly-mcp.onrender.com/health

# Poll for commands
curl https://twinkly-mcp.onrender.com/api/commands/poll

# Poll after specific command
curl "https://twinkly-mcp.onrender.com/api/commands/poll?after=cmd_000005"
```

## Card Registration

The Raspberry Pi can register its available cards with the server on startup. This allows the server to know which cards are actually available.

### Register Cards

```
POST /api/cards/register
Content-Type: application/json

{
  "cards": ["beer", "calendar", "clock", "weather", "tuborg_julebryg", ...]
}
```

**Response:**
```json
{
  "status": "registered",
  "count": 35,
  "cards": ["beer", "calendar", "clock", ...]
}
```

### Get Available Cards

```
GET /api/cards
```

**Response:**
```json
{
  "cards": ["beer", "calendar", "clock", "weather", ...]
}
```

### Recommended Registration Logic

```python
import requests

SERVER_URL = "https://twinkly-mcp.onrender.com"

def register_cards():
    """Register available cards with the MCP server on startup."""
    # Get list of available card types from twinkly-wall
    from twinkly_wall.cards import list_card_types
    cards = list_card_types()

    response = requests.post(
        f"{SERVER_URL}/api/cards/register",
        json={"cards": cards},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    print(f"Registered {data['count']} cards with MCP server")

# Call on startup
register_cards()
```

## Server Implementation Notes

- Commands are stored in-memory (not persisted across restarts)
- Maximum 100 commands retained (oldest pruned automatically)
- Command IDs are sequential: `cmd_000001`, `cmd_000002`, etc.
- ISO 8601 timestamps with timezone info
- Card registry persists in memory but resets on server restart (default cards are used as fallback)
