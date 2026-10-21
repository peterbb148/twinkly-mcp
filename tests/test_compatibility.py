"""Exercise command flows against the locked MCP, Starlette, and Pydantic versions."""

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from twinkly_mcp.queue import card_registry, command_queue
from twinkly_mcp.server import app, mcp


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Keep registry, queue, and authentication isolated between compatibility tests."""
    monkeypatch.delenv("TWINKLY_API_KEY", raising=False)
    cards = card_registry.list_cards()
    card_registry.register(["clock", "snow"])
    command_queue.clear()
    yield
    card_registry.register(cards)
    command_queue.clear()


@pytest.fixture
def client():
    """Run the combined ASGI application with its MCP lifespan enabled."""
    with TestClient(app) as test_client:
        yield test_client


def test_http_command_round_trip(client, monkeypatch):
    """Authenticated commands preserve their payloads through the Pi polling API."""
    monkeypatch.setenv("TWINKLY_API_KEY", "test-key")
    headers = {"Authorization": "Bearer test-key"}
    response = client.post(
        "/api/twinklysay", json={"text": " Hello ", "color": " gold "}, headers=headers
    )
    assert response.status_code == 200
    message_id = response.json()["command_id"]
    response = client.post("/api/run_card", json={"card_id": " CLOCK "}, headers=headers)
    assert response.status_code == 200
    card_id = response.json()["command_id"]

    response = client.get("/api/commands/poll", headers=headers)
    assert response.status_code == 200
    commands = response.json()["commands"]
    assert [(cmd["type"], cmd["payload"]) for cmd in commands] == [
        ("twinklysay", {"text": "Hello", "color": "gold"}),
        ("run_card", {"card_id": "clock"}),
    ]
    assert commands[0]["created_at"].endswith("+00:00")
    response = client.get("/api/commands/poll", params={"after": message_id}, headers=headers)
    assert [cmd["id"] for cmd in response.json()["commands"]] == [card_id]


def test_card_registration_replaces_available_cards(client):
    response = client.post("/api/cards/register", json={"cards": [" RAIN ", "rain", "snow"]})
    assert response.status_code == 200
    assert response.json()["cards"] == ["rain", "snow"]
    assert client.get("/api/cards").json() == {"cards": ["rain", "snow"]}
    assert client.post("/api/run_card", json={"card_id": "rain"}).status_code == 200
    assert client.post("/api/run_card", json={"card_id": "clock"}).status_code == 400


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("/api/twinklysay", {}),
        ("/api/twinklysay", {"text": "   "}),
        ("/api/twinklysay", {"text": "x" * 201}),
        ("/api/twinklysay", {"text": 42}),
        ("/api/run_card", {}),
        ("/api/run_card", {"card_id": "unknown"}),
        ("/api/run_card", {"card_id": 42}),
        ("/api/cards/register", {"cards": "clock"}),
        ("/api/cards/register", {"cards": [42]}),
    ],
)
def test_invalid_http_commands_do_not_enqueue(client, endpoint, payload):
    response = client.post(endpoint, json=payload)
    assert response.status_code == 400
    assert "error" in response.json()
    assert len(command_queue) == 0


@pytest.mark.parametrize("endpoint", ["/api/twinklysay", "/api/run_card", "/api/cards/register"])
def test_malformed_json_is_rejected(client, endpoint):
    response = client.post(endpoint, content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert len(command_queue) == 0


@pytest.mark.parametrize("endpoint", ["/api/twinklysay", "/api/run_card", "/api/cards/register"])
def test_write_endpoints_require_authentication(client, monkeypatch, endpoint):
    monkeypatch.setenv("TWINKLY_API_KEY", "test-key")
    assert client.post(endpoint, json={}).status_code == 401
    assert client.get("/health").status_code == 200
    assert len(command_queue) == 0


async def test_mcp_tools_round_trip():
    """The upgraded SDK discovers tools and queues commands that the Pi can consume."""
    async with Client(mcp) as mcp_client:
        tools = await mcp_client.list_tools()
        assert {tool.name for tool in tools} == {"twinklysay", "run_card", "list_cards"}
        cards = await mcp_client.call_tool("list_cards")
        assert cards.data == {"cards": ["clock", "snow"]}
        message = await mcp_client.call_tool("twinklysay", {"text": " Hello ", "color": " red "})
        card = await mcp_client.call_tool("run_card", {"card_id": " CLOCK "})
        assert message.data["status"] == card.data["status"] == "queued"
    assert [cmd.payload for cmd in command_queue.get_after()] == [
        {"text": "Hello", "color": "red"},
        {"card_id": "clock"},
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "error"),
    [
        ("twinklysay", {"text": ""}, "Text cannot be empty"),
        ("twinklysay", {"text": " "}, "Text cannot be empty"),
        ("twinklysay", {"text": "x" * 201}, "Text too long (max 200 characters)"),
        ("run_card", {"card_id": "unknown"}, "Unknown card 'unknown'"),
    ],
)
async def test_mcp_validation(tool, arguments, error):
    async with Client(mcp) as mcp_client:
        result = await mcp_client.call_tool(tool, arguments)
        assert result.data["error"] == error
    assert len(command_queue) == 0


def test_registry_normalization_and_removal():
    card_registry.clear()
    card_registry.add(" CLOCK ")
    assert card_registry.is_known("clock")
    card_registry.remove(" Clock ")
    assert card_registry.list_cards() == []
