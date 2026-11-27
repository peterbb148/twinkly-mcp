"""Tests for the now-playing HTTP contract and bounded state storage."""

import pytest
from httpx import ASGITransport, AsyncClient

from twinkly_mcp import now_playing
from twinkly_mcp.queue import command_queue
from twinkly_mcp.server import app

_PATH = "/api/now-playing"
_HEADERS = {"Authorization": "Bearer local-test-key"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TWINKLY_API_KEY", "local-test-key")
    monkeypatch.setattr(now_playing, "_latest", None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_HEADERS)


def snapshot(**overrides):
    return {
        "version": 1,
        "publisher": 100,
        "sequence": 10,
        "state": "playing",
        "orientation": "left",
        "mirror_h": True,
        "mirror_v": False,
        "playback": {
            "instance": 8,
            "card_id": "lunch_horizontal",
            "elapsed_ms": 80,
            "replay": {"renderer": "lunch_horizontal/v1", "meal": "Red Cabbage"},
        },
        **overrides,
    }


@pytest.mark.asyncio
async def test_snapshots_are_authenticated_current_and_aged(client, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(now_playing, "monotonic", lambda: clock[0])
    async with client:
        assert (await client.get(_PATH, headers={"Authorization": ""})).status_code == 401
        assert (await client.post(_PATH, headers={"Authorization": ""})).status_code == 401
        assert (await client.get(_PATH)).json() == {"snapshot": None, "age_ms": None}
        assert (await client.post(_PATH, json=snapshot())).status_code == 200
        clock[0] += 1.25
        observed = await client.get(_PATH)
        assert observed.json() == {"snapshot": snapshot(), "age_ms": 1250}
        assert observed.headers["cache-control"] == "no-store"
        assert (await client.post(_PATH, json=snapshot(sequence=9))).status_code == 409
        new_state = snapshot(publisher=101, sequence=1, state="off", playback=None)
        assert (await client.post(_PATH, json=new_state)).status_code == 200
        assert (await client.post(_PATH, json=snapshot(sequence=100))).status_code == 409
        assert (await client.get(_PATH)).json()["snapshot"] == new_state
        monkeypatch.setattr(now_playing, "_latest", None)
        assert (await client.get(_PATH)).json()["snapshot"] is None
        assert (await client.post(_PATH, json=new_state)).status_code == 200


@pytest.mark.asyncio
async def test_refuses_frames_unknown_payloads_and_oversize_bodies(client):
    async with client:
        assert (await client.post(_PATH, content=b"x" * 2049)).status_code == 413
        assert (await client.post(_PATH, content=b"not json")).status_code == 400
        assert (await client.post(_PATH, json=snapshot(frame=[[0]]))).status_code == 400
        assert (await client.post(_PATH, json=snapshot(state="idle"))).status_code == 400
        assert (await client.post(_PATH, json=snapshot(playback=None))).status_code == 400
        playing = snapshot()["playback"]
        playing["replay"] = {"renderer": "pacman_up/v1", "frame": [1]}
        assert (await client.post(_PATH, json=snapshot(playback=playing))).status_code == 400
        playing["replay"] = {
            "renderer": "pacman_up/v1",
            "theme": "trees",
            "speed": 15,
            "repeats": 1,
            "num_items": 4,
            "color": [255, 255, 0],
        }
        assert (await client.post(_PATH, json=snapshot(playback=playing))).status_code == 200
        assert (await client.get(_PATH)).json()["snapshot"]["playback"]["replay"] == playing[
            "replay"
        ]


@pytest.mark.asyncio
async def test_now_playing_does_not_consume_or_add_wall_commands(client):
    command_queue.clear()
    try:
        sent = command_queue.add("run_card", {"card_id": "pacman_up"})
        async with client:
            active = snapshot()["playback"]
            active["replay"] = None
            assert (await client.post(_PATH, json=snapshot(playback=active))).status_code == 200
            await client.get(_PATH)
            polled = (await client.get("/api/commands/poll")).json()
        assert [command["id"] for command in polled["commands"]] == [sent.id]
    finally:
        command_queue.clear()
