"""Static phone remote and its preset-only API."""

import hashlib
import hmac
import os
import time
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from .queue import card_registry, command_queue

ASSETS = Path(__file__).with_name("remote_assets")
SESSION_COOKIE = "twinkly_remote"
SESSION_SECONDS = 2 * 60 * 60
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


def remote_key() -> str | None:
    """Return the remote key only when the privileged API is protected separately."""
    key = os.environ.get("TWINKLY_REMOTE_KEY")
    api_key = os.environ.get("TWINKLY_API_KEY")
    if not key or not api_key or hmac.compare_digest(key.encode(), api_key.encode()):
        return None
    return key


def error_response(message: str, status_code: int) -> JSONResponse:
    """Return a remote API error without including credentials."""
    return JSONResponse({"error": message}, status_code=status_code, headers=HEADERS)


def signature(key: str, expiry: str) -> str:
    """Sign a remote session expiry with a key scoped to the remote."""
    return hmac.new(key.encode(), f"remote-session:{expiry}".encode(), hashlib.sha256).hexdigest()


def has_session(request: Request) -> bool:
    """Check that the cookie is current and signed with the active remote key."""
    key = remote_key()
    if key is None:
        return False
    expiry, _, digest = request.cookies.get(SESSION_COOKIE, "").partition(".")
    if not expiry.isascii() or not expiry.isdecimal() or len(expiry) > 12:
        return False
    return int(expiry) > time.time() and hmac.compare_digest(
        digest.encode(), signature(key, expiry).encode()
    )


def approved_presets() -> list[str]:
    """Return configured presets that the wall can play."""
    approved = {
        preset.strip().lower()
        for preset in os.environ.get("TWINKLY_REMOTE_PRESETS", "").split(",")
        if preset.strip()
    }
    return sorted(approved.intersection(card_registry.list_wall_cards()))


async def unlock(request: Request) -> Response:
    """Exchange the QR credential for a short-lived browser session."""
    key = remote_key()
    if key is None:
        return error_response("Remote unavailable", 503)
    provided = request.headers.get("X-Twinkly-Remote-Key", "")
    if not hmac.compare_digest(provided.encode(), key.encode()):
        return error_response("Invalid remote key", 401)
    expiry = str(int(time.time()) + SESSION_SECONDS)
    response = Response(status_code=204, headers=HEADERS)
    response.set_cookie(
        SESSION_COOKIE,
        f"{expiry}.{signature(key, expiry)}",
        max_age=SESSION_SECONDS,
        path="/remote",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response


async def list_presets(request: Request) -> JSONResponse:
    """List cards available to an authenticated guest."""
    if not has_session(request):
        return error_response("Remote session required", 401)
    return JSONResponse({"presets": approved_presets()}, headers=HEADERS)


async def play_preset(request: Request) -> JSONResponse:
    """Queue a card only if it is approved and available on the wall."""
    if not has_session(request):
        return error_response("Remote session required", 401)
    # Cross-origin forms cannot send JSON. The remote endpoints do not enable CORS.
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        return error_response("Expected JSON", 415)
    try:
        body = await request.json()
    except ValueError:
        return error_response("Invalid JSON", 400)
    if not isinstance(body, dict) or set(body) != {"preset"} or not isinstance(body["preset"], str):
        return error_response("Expected a preset name", 400)
    preset = body["preset"]
    if preset not in approved_presets():
        return error_response("Preset unavailable or not approved", 403)
    command = command_queue.add("run_card", {"card_id": preset})
    return JSONResponse({"status": "queued", "command_id": command.id}, headers=HEADERS)


def asset_route(path: str, filename: str, media_type: str) -> Route:
    """Serve a fixed asset without exposing other package files."""

    async def asset(request: Request) -> Response:
        return FileResponse(ASSETS / filename, media_type=media_type, headers=HEADERS)

    return Route(path, asset, methods=["GET"], name=filename)


routes = [
    asset_route("/remote", "index.html", "text/html"),
    asset_route("/remote/app.css", "app.css", "text/css"),
    asset_route("/remote/app.js", "app.js", "text/javascript"),
    asset_route("/remote/app.webmanifest", "app.webmanifest", "application/manifest+json"),
    asset_route("/remote/icon-192.png", "icon-192.png", "image/png"),
    asset_route("/remote/icon-512.png", "icon-512.png", "image/png"),
    Route("/remote/unlock", unlock, methods=["POST"]),
    Route("/remote/presets", list_presets, methods=["GET"]),
    Route("/remote/play", play_preset, methods=["POST"]),
]
REMOTE_PATHS = frozenset(route.path for route in routes)
