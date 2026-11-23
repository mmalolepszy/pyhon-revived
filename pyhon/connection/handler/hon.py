import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import aiohttp
from typing_extensions import Self
from yarl import URL

from pyhon.connection.auth import HonAuth
from pyhon.connection.device import HonDevice
from pyhon.connection.handler.base import ConnectionHandler
from pyhon.exceptions import HonAuthenticationError, NoAuthenticationException
from pyhon.typedefs import Callback

_LOGGER = logging.getLogger(__name__)


class HonConnectionHandler(ConnectionHandler):
    def __init__(
        self,
        email: str,
        password: str,
        session: Optional[aiohttp.ClientSession] = None,
        mobile_id: str = "",
        refresh_token: str = "",
    ) -> None:
        super().__init__(session=session)
        self._device: HonDevice = HonDevice(mobile_id)
        self._email: str = email
        self._password: str = password
        self._refresh_token: str = refresh_token
        if not self._email:
            raise HonAuthenticationError("An email address must be specified")
        if not self._password:
            raise HonAuthenticationError("A password address must be specified")
        self._auth: Optional[HonAuth] = None

    @property
    def auth(self) -> HonAuth:
        if self._auth is None:
            raise NoAuthenticationException()
        return self._auth

    @property
    def device(self) -> HonDevice:
        return self._device

    async def create(self) -> Self:
        await super().create()
        self._auth = HonAuth(
            self.session,
            self._email,
            self._password,
            self._device,
        )
        return self

    async def _check_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        if not (self.auth.cognito_token and self.auth.id_token):
            await self.auth.authenticate()
        self._refresh_token = self.auth.refresh_token
        headers["cognito-token"] = self.auth.cognito_token
        headers["id-token"] = self.auth.id_token
        return self._HEADERS | headers

    @asynccontextmanager
    async def _intercept(
        self, method: Callback, url: str | URL, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[aiohttp.ClientResponse]:
        for attempt in range(3):
            kwargs["headers"] = await self._check_headers(kwargs.get("headers", {}))
            async with method(url, *args, **kwargs) as response:
                needs_retry = response.status in (401, 403) or (
                    (self.auth.token_expires_soon and attempt == 0)
                    or (self.auth.token_is_expired and attempt == 1)
                )
                if not needs_retry:
                    try:
                        await response.json()
                    except json.JSONDecodeError as exc:
                        _LOGGER.warning(
                            "%s - JsonDecodeError %s - %s",
                            response.request_info.url,
                            response.status,
                            await response.text(),
                        )
                        raise HonAuthenticationError("Decode Error") from exc
                    yield response
                    return
                if attempt == 1:
                    _LOGGER.info(
                        "%s - Error %s - %s",
                        response.request_info.url,
                        response.status,
                        await response.text(),
                    )
                elif attempt == 2:
                    _LOGGER.error(
                        "%s - Error %s - %s",
                        response.request_info.url,
                        response.status,
                        await response.text(),
                    )
                    raise HonAuthenticationError("Login failure")
            if attempt == 0:
                _LOGGER.info("Try refreshing token...")
                await self.auth.refresh(self._refresh_token)
            else:
                await self.create()
