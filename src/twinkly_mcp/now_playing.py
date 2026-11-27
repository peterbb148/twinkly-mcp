"""Authenticated HTTP storage for the wall's latest playback snapshot."""

from time import monotonic
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse

_MAX_BYTES = 2048
_HEADERS = {"Cache-Control": "no-store"}


class PacmanReplay(BaseModel):
    """Effective parameters for the deterministic Pac-Man Up renderer."""

    model_config = ConfigDict(extra="forbid", strict=True)
    renderer: Literal["pacman_up/v1"]
    theme: str = Field(pattern=r"^[a-z_]{1,32}$")
    speed: float = Field(gt=0, le=1000)
    repeats: int = Field(ge=1, le=100)
    num_items: int = Field(ge=0, le=100)
    color: list[Annotated[int, Field(ge=0, le=255)]] = Field(min_length=3, max_length=3)


class LunchReplay(BaseModel):
    """Meal already selected on the wall for this playback."""

    model_config = ConfigDict(extra="forbid", strict=True)
    renderer: Literal["lunch_horizontal/v1"]
    meal: str = Field(min_length=1, max_length=250)


class Playback(BaseModel):
    """The active card and the inputs needed for local replay, if supported."""

    model_config = ConfigDict(extra="forbid", strict=True)
    instance: int = Field(ge=1)
    card_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    elapsed_ms: int = Field(ge=0)
    replay: Annotated[PacmanReplay | LunchReplay, Field(discriminator="renderer")] | None


class Snapshot(BaseModel):
    """Versioned now-playing state sent by a single wall daemon."""

    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1]
    publisher: int = Field(ge=1)
    sequence: int = Field(ge=1)
    state: Literal["idle", "off", "playing"]
    orientation: Literal[
        "top", "bottom", "left", "right", "horizontal", "vertical_left", "vertical_right"
    ]
    mirror_h: bool
    mirror_v: bool
    playback: Playback | None


_latest: tuple[Snapshot, float] | None = None


async def publish_now_playing(request: Request) -> JSONResponse:
    """Replace the snapshot only with newer wall state."""
    global _latest
    body = bytearray()
    try:
        async for chunk in request.stream():
            if len(body) + len(chunk) > _MAX_BYTES:
                return JSONResponse({"error": "Snapshot too large"}, 413, headers=_HEADERS)
            body.extend(chunk)
        snapshot = Snapshot.model_validate_json(body)
    except (ValidationError, ClientDisconnect):
        return JSONResponse({"error": "Invalid now-playing snapshot"}, 400, headers=_HEADERS)

    if (snapshot.state == "playing") != (snapshot.playback is not None):
        return JSONResponse({"error": "Invalid playback state"}, 400, headers=_HEADERS)
    if _latest is not None:
        current, _ = _latest
        if (snapshot.publisher, snapshot.sequence) <= (current.publisher, current.sequence):
            return JSONResponse({"error": "Out-of-order snapshot"}, 409, headers=_HEADERS)
    _latest = (snapshot, monotonic())
    return JSONResponse({"stored": True}, headers=_HEADERS)


async def get_now_playing(request: Request) -> JSONResponse:
    """Return current state and server-measured age without retaining history."""
    if _latest is None:
        return JSONResponse({"snapshot": None, "age_ms": None}, headers=_HEADERS)
    snapshot, received = _latest
    age_ms = round((monotonic() - received) * 1000)
    return JSONResponse({"snapshot": snapshot.model_dump(), "age_ms": age_ms}, headers=_HEADERS)
