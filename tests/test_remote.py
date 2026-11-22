"""Exercise the QR session and its restricted command surface."""

from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from twinkly_mcp import remote, server
from twinkly_mcp.queue import CardRegistry, CommandQueue

REMOTE_KEY = "local-test-remote-key"
API_KEY = "local-test-mcp-key"
QR_HEADER = {"X-Twinkly-Remote-Key": REMOTE_KEY}


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    """Configure distinct credentials and an isolated wall registry and queue."""
    monkeypatch.setenv("TWINKLY_API_KEY", API_KEY)
    monkeypatch.setenv("TWINKLY_REMOTE_KEY", REMOTE_KEY)
    monkeypatch.setenv("TWINKLY_REMOTE_PRESETS", "party-flame, missing-card")
    registry = CardRegistry()
    registry.register(["party-flame", "clock"])
    queue = CommandQueue()
    for module in (server, remote):
        monkeypatch.setattr(module, "card_registry", registry)
        monkeypatch.setattr(module, "command_queue", queue)
    async with AsyncClient(
        transport=ASGITransport(app=server.app), base_url="https://test"
    ) as browser:
        yield browser


async def test_static_page_and_install_assets_are_available_before_unlock(client: AsyncClient):
    response = await client.get("/remote#key=unused-in-http")
    assert response.status_code == 200
    assert 'id="presets" hidden' in response.text
    assert REMOTE_KEY not in response.text
    assert response.headers["referrer-policy"] == "no-referrer"

    manifest = (await client.get("/remote/app.webmanifest")).json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/remote"
    for icon in manifest["icons"]:
        response = await client.get(icon["src"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    for resource in ("app.css", "app.js"):
        assert (await client.get(f"/remote/{resource}")).status_code == 200


@pytest.mark.parametrize("headers", [{}, {"X-Twinkly-Remote-Key": API_KEY}])
async def test_missing_or_wrong_qr_key_leaves_remote_locked(client: AsyncClient, headers: dict):
    assert (await client.post("/remote/unlock", headers=headers)).status_code == 401
    assert (await client.get("/remote/presets")).status_code == 401
    assert (await client.post("/remote/play", json={"preset": "party-flame"})).status_code == 401


async def test_qr_session_lists_and_plays_only_approved_available_presets(client: AsyncClient):
    unlocked = await client.post("/remote/unlock", headers=QR_HEADER)
    assert unlocked.status_code == 204
    cookie = unlocked.headers["set-cookie"].lower()
    assert all(
        flag in cookie
        for flag in ("secure", "httponly", "samesite=strict", "path=/remote", "max-age=7200")
    )
    assert REMOTE_KEY not in cookie
    assert (await client.get("/remote/presets")).json() == {"presets": ["party-flame"]}
    for preset in ("clock", "missing-card"):
        assert (await client.post("/remote/play", json={"preset": preset})).status_code == 403
    assert len(remote.command_queue) == 0

    played = await client.post("/remote/play", json={"preset": "party-flame"})
    assert played.status_code == 200
    result = await client.get("/api/commands/poll", headers={"Authorization": f"Bearer {API_KEY}"})
    (command,) = result.json()["commands"]
    assert command["id"] == played.json()["command_id"]
    assert command["type"] == "run_card"
    assert command["payload"] == {"card_id": "party-flame"}


async def test_guest_cookie_cannot_authorize_privileged_routes(client: AsyncClient):
    await client.post("/remote/unlock", headers=QR_HEADER)
    guest_cookie = f"{remote.SESSION_COOKIE}={client.cookies[remote.SESSION_COOKIE]}"
    for method, path in [
        ("POST", "/api/twinklysay"),
        ("GET", "/api/commands/poll"),
        ("POST", "/api/cards/register"),
        ("POST", "/api/run_card"),
        ("POST", "/mcp"),
    ]:
        response = await client.request(method, path, headers={"Cookie": guest_cookie})
        assert response.status_code == 401
    assert len(remote.command_queue) == 0


async def test_play_requires_json_with_only_a_preset_name(client: AsyncClient):
    await client.post("/remote/unlock", headers=QR_HEADER)
    assert (await client.post("/remote/play", data={"preset": "party-flame"})).status_code == 415
    assert (
        await client.post("/remote/play", content="!", headers={"Content-Type": "application/json"})
    ).status_code == 400
    for payload in (["party-flame"], {"preset": 1}, {"preset": "party-flame", "text": "Hello"}):
        assert (await client.post("/remote/play", json=payload)).status_code == 400
    assert len(remote.command_queue) == 0


async def test_session_expires_and_same_qr_can_unlock_again(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    clock = Mock()
    clock.time.return_value = 1000
    monkeypatch.setattr(remote, "time", clock)
    assert (await client.post("/remote/unlock", headers=QR_HEADER)).status_code == 204
    clock.time.return_value += remote.SESSION_SECONDS
    assert (await client.get("/remote/presets")).status_code == 401
    assert (await client.post("/remote/unlock", headers=QR_HEADER)).status_code == 204
    assert (await client.get("/remote/presets")).status_code == 200


async def test_remote_key_rotation_invalidates_sessions(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await client.post("/remote/unlock", headers=QR_HEADER)
    monkeypatch.setenv("TWINKLY_REMOTE_KEY", "replacement-key")
    assert (await client.get("/remote/presets")).status_code == 401
    assert (await client.post("/remote/unlock", headers=QR_HEADER)).status_code == 401


@pytest.mark.parametrize("api_key", ["", REMOTE_KEY])
async def test_remote_requires_a_distinct_privileged_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_key: str
):
    monkeypatch.setenv("TWINKLY_API_KEY", api_key)
    assert (await client.post("/remote/unlock", headers=QR_HEADER)).status_code == 503


async def test_render_requires_api_key_except_for_health(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("TWINKLY_API_KEY")
    monkeypatch.delenv("TWINKLY_REMOTE_KEY")
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/api/cards")).status_code == 503
