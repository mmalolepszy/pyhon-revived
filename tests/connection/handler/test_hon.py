import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from pyhon.connection.handler.hon import HonConnectionHandler
from pyhon.exceptions import HonAuthenticationError


class FakeResponse:
    def __init__(self, status: int, body: str = "{}") -> None:
        self.status = status
        self.request_info = SimpleNamespace(url="https://example.test/api")
        self._body = body

    async def json(self) -> Any:
        return json.loads(self._body)

    async def text(self) -> str:
        return self._body


class FakeAuth:
    cognito_token = "cognito"
    id_token = "id"
    refresh_token = "refresh"

    def __init__(self, events: list[str], expires_soon: bool = False) -> None:
        self.events = events
        self.token_expires_soon = expires_soon
        self.token_is_expired = False

    async def refresh(self, _refresh_token: str) -> bool:
        self.events.append("refresh")
        self.token_expires_soon = False
        return True

    async def authenticate(self) -> None:
        self.events.append("authenticate")


def make_handler(
    statuses: list[int], body: str = "{}", expires_soon: bool = False
) -> tuple[HonConnectionHandler, list[str]]:
    events: list[str] = []
    responses = list(statuses)

    @asynccontextmanager
    async def fake_get(_url: str, **_kwargs: Any) -> AsyncGenerator[FakeResponse]:
        status = responses.pop(0)
        events.append(f"request {status}")
        try:
            yield FakeResponse(status, body)
        finally:
            events.append(f"close {status}")

    async def fake_create() -> HonConnectionHandler:
        events.append("create")
        return handler

    handler = HonConnectionHandler(
        "user@example.test",
        "password",
        session=SimpleNamespace(get=fake_get),  # type: ignore[arg-type]
    )
    handler._auth = FakeAuth(events, expires_soon)  # type: ignore[assignment]  # pylint: disable=protected-access
    handler.create = fake_create  # type: ignore[method-assign]
    return handler, events


async def get_status(handler: HonConnectionHandler) -> int:
    async with handler.get("https://example.test/api") as response:
        return response.status


def steps(events: list[str]) -> list[str]:
    return [event for event in events if not event.startswith("close")]


async def test_success_needs_one_request() -> None:
    handler, events = make_handler([200])
    assert await get_status(handler) == 200
    assert events == ["request 200", "close 200"]


async def test_refresh_token_after_unauthorized() -> None:
    handler, events = make_handler([401, 200])
    assert await get_status(handler) == 200
    assert steps(events) == ["request 401", "refresh", "request 200"]


async def test_recreate_after_second_unauthorized() -> None:
    handler, events = make_handler([401, 403, 200])
    assert await get_status(handler) == 200
    assert steps(events) == [
        "request 401",
        "refresh",
        "request 403",
        "create",
        "request 200",
    ]


async def test_login_failure_after_three_unauthorized() -> None:
    handler, events = make_handler([401, 401, 401])
    with pytest.raises(HonAuthenticationError, match="Login failure"):
        await get_status(handler)
    assert events.count("request 401") == 3


async def test_refresh_when_token_expires_soon() -> None:
    handler, events = make_handler([200, 200], expires_soon=True)
    assert await get_status(handler) == 200
    assert steps(events) == ["request 200", "refresh", "request 200"]


async def test_response_closed_before_retry() -> None:
    handler, events = make_handler([401, 403, 200])
    await get_status(handler)
    assert events == [
        "request 401",
        "close 401",
        "refresh",
        "request 403",
        "close 403",
        "create",
        "request 200",
        "close 200",
    ]


async def test_invalid_json_is_decode_error() -> None:
    handler, _ = make_handler([200], body="not json")
    with pytest.raises(HonAuthenticationError, match="Decode Error"):
        await get_status(handler)


async def test_caller_exception_is_not_replaced() -> None:
    handler, _ = make_handler([200])
    with pytest.raises(json.JSONDecodeError):
        async with handler.get("https://example.test/api"):
            json.loads("not json")
