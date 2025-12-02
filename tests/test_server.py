"""Tests for the server HTTP endpoints."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from twinkly_mcp.queue import command_queue
from twinkly_mcp.server import app


@pytest.fixture(autouse=True)
def clear_queue():
    """Clear the command queue before each test."""
    command_queue.clear()
    yield
    command_queue.clear()


@pytest.fixture(autouse=True)
def clear_api_key():
    """Clear API key env var before each test."""
    original = os.environ.pop("TWINKLY_API_KEY", None)
    yield
    if original:
        os.environ["TWINKLY_API_KEY"] = original


@pytest.fixture
def api_key():
    """Set up API key for auth tests."""
    key = "test-secret-key"
    os.environ["TWINKLY_API_KEY"] = key
    return key


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check returns healthy status."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "twinkly-mcp"

    @pytest.mark.asyncio
    async def test_health_check_no_auth_required(self, api_key):
        """Test health check doesn't require authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200


class TestPollEndpoint:
    """Tests for /api/commands/poll endpoint."""

    @pytest.mark.asyncio
    async def test_poll_empty_queue(self):
        """Test polling empty queue returns empty list."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/commands/poll")

        assert response.status_code == 200
        data = response.json()
        assert data["commands"] == []

    @pytest.mark.asyncio
    async def test_poll_with_commands(self):
        """Test polling returns queued commands."""
        command_queue.add("twinklysay", {"text": "Hello"})
        command_queue.add("run_card", {"card_id": "clock"})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/commands/poll")

        assert response.status_code == 200
        data = response.json()
        assert len(data["commands"]) == 2
        assert data["commands"][0]["type"] == "twinklysay"
        assert data["commands"][1]["type"] == "run_card"

    @pytest.mark.asyncio
    async def test_poll_with_after_param(self):
        """Test polling with after parameter."""
        cmd1 = command_queue.add("twinklysay", {"text": "First"})
        command_queue.add("twinklysay", {"text": "Second"})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/commands/poll?after={cmd1.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["commands"]) == 1
        assert data["commands"][0]["payload"]["text"] == "Second"

    @pytest.mark.asyncio
    async def test_poll_requires_auth(self, api_key):
        """Test poll endpoint requires authentication when API key is set."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/commands/poll")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_poll_with_valid_auth(self, api_key):
        """Test poll endpoint accepts valid authentication."""
        command_queue.add("twinklysay", {"text": "Hello"})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/commands/poll",
                headers={"Authorization": f"Bearer {api_key}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["commands"]) == 1

    @pytest.mark.asyncio
    async def test_poll_with_invalid_auth(self, api_key):
        """Test poll endpoint rejects invalid authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/commands/poll",
                headers={"Authorization": "Bearer wrong-key"},
            )

        assert response.status_code == 401
