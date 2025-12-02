"""Twinkly MCP server with HTTP API for Raspberry Pi polling."""

import os

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .queue import card_registry, command_queue


def get_api_key() -> str | None:
    """Get API key from environment."""
    return os.environ.get("TWINKLY_API_KEY")


# ============================================================
# FastMCP Server with MCP Tools
# ============================================================

mcp = FastMCP(
    name="Twinkly MCP",
    instructions="Remote control for Twinkly LED wall. Use twinklysay to display messages, run_card to trigger animations.",
)


@mcp.tool()
def twinklysay(text: str, color: str | None = None) -> dict:
    """Display a text message on the Twinkly LED wall.

    The message will scroll across the 50x10 LED matrix.

    Args:
        text: The message to display (max 200 characters)
        color: Optional color name (red, green, blue, yellow, white, etc.) or hex code (#FF0000)

    Returns:
        Confirmation with command ID
    """
    if not text or not text.strip():
        return {"error": "Text cannot be empty"}

    text = text.strip()
    if len(text) > 200:
        return {"error": "Text too long (max 200 characters)"}

    payload = {"text": text}
    if color:
        payload["color"] = color.strip()

    cmd = command_queue.add("twinklysay", payload)

    return {
        "status": "queued",
        "command_id": cmd.id,
        "message": f"Message queued: '{text[:50]}{'...' if len(text) > 50 else ''}'",
    }


@mcp.tool()
def run_card(card_id: str) -> dict:
    """Run a specific display card on the Twinkly LED wall.

    Args:
        card_id: The card type to display. Available cards:
            clock, weather, pacman, snow, beer, rainbow, matrix,
            fireworks, ocean, lava, fire, countdown, and more.

    Returns:
        Confirmation with command ID
    """
    card_id = card_id.lower().strip()

    if not card_registry.is_known(card_id):
        return {
            "error": f"Unknown card '{card_id}'",
            "available_cards": card_registry.list_cards(),
        }

    cmd = command_queue.add("run_card", {"card_id": card_id})

    return {
        "status": "queued",
        "command_id": cmd.id,
        "message": f"Card '{card_id}' queued for display",
    }


@mcp.tool()
def list_cards() -> dict:
    """List all available display cards.

    Returns:
        List of card IDs that can be used with run_card
    """
    return {"cards": card_registry.list_cards()}


# ============================================================
# HTTP API for Raspberry Pi
# ============================================================


async def poll_commands(request: Request) -> JSONResponse:
    """GET /api/commands/poll - Raspberry Pi polls for new commands.

    Query params:
        after: Last command ID seen (optional)

    Returns:
        List of commands newer than 'after'
    """
    last_id = request.query_params.get("after")
    commands = command_queue.get_after(last_id)

    return JSONResponse(
        {
            "commands": [
                {
                    "id": cmd.id,
                    "type": cmd.type,
                    "payload": cmd.payload,
                    "created_at": cmd.created_at.isoformat(),
                }
                for cmd in commands
            ]
        }
    )


async def health_check(request: Request) -> JSONResponse:
    """GET /health - Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "twinkly-mcp"})


async def register_cards(request: Request) -> JSONResponse:
    """POST /api/cards/register - Register available cards from the Pi.

    Body:
        {"cards": ["card_id_1", "card_id_2", ...]}

    This replaces the current card list with the provided list.
    """
    try:
        body = await request.json()
        cards = body.get("cards", [])

        if not isinstance(cards, list):
            return JSONResponse(
                {"error": "cards must be a list"},
                status_code=400,
            )

        card_registry.register(cards)

        return JSONResponse({
            "status": "registered",
            "count": len(cards),
            "cards": card_registry.list_cards(),
        })
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=400,
        )


async def get_cards(request: Request) -> JSONResponse:
    """GET /api/cards - Get list of registered cards."""
    return JSONResponse({
        "cards": card_registry.list_cards(),
    })


# ============================================================
# Authentication Middleware
# ============================================================


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication middleware.

    Validates Bearer token in Authorization header against TWINKLY_API_KEY.
    Health check endpoint is always accessible.
    """

    async def dispatch(self, request: Request, call_next):
        # Always allow health check
        if request.url.path == "/health":
            return await call_next(request)

        api_key = get_api_key()

        # Skip auth if no key configured (development mode)
        if not api_key:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Authentication required. Provide Authorization: Bearer <token>"},
                status_code=401,
            )

        token = auth_header.removeprefix("Bearer ").strip()

        if token != api_key:
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        return await call_next(request)


# ============================================================
# Combined ASGI Application
# ============================================================

# Get MCP ASGI app
mcp_app = mcp.http_app(path="/mcp")

# Create combined Starlette app with MCP lifespan
app = Starlette(
    routes=[
        # Custom HTTP endpoints (must be before MCP mount to be matched first)
        Route("/api/commands/poll", poll_commands, methods=["GET"]),
        Route("/api/cards", get_cards, methods=["GET"]),
        Route("/api/cards/register", register_cards, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
        # Mount MCP server (catch-all at root)
        Mount("/", app=mcp_app),
    ],
    middleware=[
        Middleware(APIKeyAuthMiddleware),
    ],
    lifespan=mcp_app.lifespan,
)


def main():
    """Run the server directly (for development)."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
