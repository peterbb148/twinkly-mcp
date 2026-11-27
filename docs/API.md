# Twinkly Wall HTTP API

Control your Twinkly LED wall via simple HTTP requests.

**Base URL:** `https://twinkly-mcp.onrender.com`

## Authentication

When `TWINKLY_API_KEY` is set, all endpoints (except `/health`) require:

```
Authorization: Bearer YOUR_API_KEY
```

If no API key is configured, endpoints are publicly accessible.

---

## Endpoints

### Send Message

Display scrolling text on the LED wall.

```
POST /api/twinklysay
```

**Request Body:**
```json
{
  "text": "Hello World!",
  "color": "red"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Message to display (max 200 chars) |
| `color` | string | No | Color name or hex code |

**Colors:** `red`, `green`, `blue`, `yellow`, `white`, `orange`, `purple`, `pink`, `cyan`, or hex like `#FF0000`

**Response:**
```json
{
  "status": "queued",
  "command_id": "cmd_000001",
  "message": "Message queued: 'Hello World!'"
}
```

**Example:**
```bash
curl -X POST https://twinkly-mcp.onrender.com/api/twinklysay \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello!", "color": "green"}'
```

---

### Run Card

Display a visual card/animation on the LED wall.

```
POST /api/run_card
```

**Request Body:**
```json
{
  "card_id": "beer"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_id` | string | Yes | Card identifier |

**Response:**
```json
{
  "status": "queued",
  "command_id": "cmd_000002",
  "message": "Card 'beer' queued for display"
}
```

**Example:**
```bash
curl -X POST https://twinkly-mcp.onrender.com/api/run_card \
  -H "Content-Type: application/json" \
  -d '{"card_id": "fireworks"}'
```

---

### List Cards

Get all available card types.

```
GET /api/cards
```

**Response:**
```json
{
  "cards": [
    "beer", "calendar", "clock", "coffee", "confetti",
    "countdown", "fire", "fireworks", "lava", "matrix",
    "ocean", "pacman", "rainbow", "snow", "weather", ...
  ]
}
```

**Example:**
```bash
curl https://twinkly-mcp.onrender.com/api/cards
```

---

### Poll Commands (for Raspberry Pi)

Retrieve queued commands for execution.

```
GET /api/commands/poll
GET /api/commands/poll?after=cmd_000005
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `after` | string | No | Return only commands after this ID |

**Response:**
```json
{
  "commands": [
    {
      "id": "cmd_000006",
      "type": "twinklysay",
      "payload": {"text": "Hello!", "color": "red"},
      "created_at": "2025-12-02T19:00:00.000000+00:00"
    }
  ]
}
```

**Example:**
```bash
# Get all commands
curl https://twinkly-mcp.onrender.com/api/commands/poll

# Get commands after specific ID
curl "https://twinkly-mcp.onrender.com/api/commands/poll?after=cmd_000005"
```

---

### Register Cards (for Raspberry Pi)

Register available cards from the Pi.

```
POST /api/cards/register
```

**Request Body:**
```json
{
  "cards": ["beer", "clock", "weather", "custom_card"]
}
```

**Response:**
```json
{
  "status": "registered",
  "count": 4,
  "cards": ["beer", "clock", "custom_card", "weather"]
}
```

---

### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "twinkly-mcp"
}
```

---

## Quick Examples

```bash
# Say "Merry Christmas" in red
curl -X POST https://twinkly-mcp.onrender.com/api/twinklysay \
  -H "Content-Type: application/json" \
  -d '{"text": "Merry Christmas!", "color": "red"}'

# Show the snow animation
curl -X POST https://twinkly-mcp.onrender.com/api/run_card \
  -H "Content-Type: application/json" \
  -d '{"card_id": "snow"}'

# Show the clock
curl -X POST https://twinkly-mcp.onrender.com/api/run_card \
  -H "Content-Type: application/json" \
  -d '{"card_id": "clock"}'

# List all available cards
curl https://twinkly-mcp.onrender.com/api/cards
```

---

## Error Responses

**400 Bad Request:**
```json
{"error": "Text cannot be empty"}
{"error": "Unknown card 'invalid'", "available_cards": [...]}
```

**401 Unauthorized:** (when API key is required)
```json
{"error": "Authentication required. Provide Authorization: Bearer <token>"}
```

### Now playing

`POST /api/now-playing` publishes the latest wall state. `GET /api/now-playing`
returns `{"snapshot": ..., "age_ms": ...}`. Both use the existing bearer
authentication. A server with no snapshot reports both fields as null.

A version 1 playing snapshot looks like this.

```json
{
  "version": 1,
  "publisher": 1800000000000000000,
  "sequence": 12,
  "state": "playing",
  "orientation": "left",
  "mirror_h": true,
  "mirror_v": false,
  "playback": {
    "instance": 10,
    "card_id": "lunch_horizontal",
    "elapsed_ms": 450,
    "replay": {"renderer": "lunch_horizontal/v1", "meal": "Red Cabbage"}
  }
}
```

All keys shown are required. Use `"playback": null` for `idle` and `off`.
For a playing card whose renderer has no local replay support, use
`"replay": null` inside the playback object. Unknown fields are rejected.

| Replay renderer | Required fields in addition to `renderer` |
| --- | --- |
| `lunch_horizontal/v1` | `meal`, the selected meal string, up to 250 characters |
| `pacman_up/v1` | `theme` (name), `speed` (positive pixels/second, up to 1000), `num_items` (0–100), `repeats` (1–100), `color` (three RGB bytes) |

Use one positive integer `publisher` for the life of the wall daemon. The client
uses its startup Unix timestamp in nanoseconds. Increase `sequence` on every
update and heartbeat. The server accepts strictly increasing
`(publisher, sequence)` pairs. Use a higher publisher value before restarting
the sequence on daemon restart. An older or duplicate update returns HTTP
409. Invalid or incomplete payloads return HTTP 400, and requests larger
than 2,048 bytes return HTTP 413.

The server stores only the last snapshot in memory. Age is measured from
server receipt. The terminal watcher treats it as stale after 30 seconds.
