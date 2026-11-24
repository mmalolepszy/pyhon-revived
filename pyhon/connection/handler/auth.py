from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, List, Tuple, Any, Dict

import aiohttp
from yarl import URL

from pyhon import const, log
from pyhon.connection.handler.base import ConnectionHandler
from pyhon.helper import redact_url
from pyhon.typedefs import Callback

_LOGGER = log.get_logger(__name__)


class HonAuthConnectionHandler(ConnectionHandler):
    _HEADERS = {"user-agent": const.USER_AGENT, "x-api-key": const.API_KEY}

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        super().__init__(session)
        self._called_urls: List[Tuple[int, str]] = []

    @property
    def called_urls(self) -> List[Tuple[int, str]]:
        return self._called_urls

    @called_urls.setter
    def called_urls(self, called_urls: List[Tuple[int, str]]) -> None:
        self._called_urls = called_urls

    @asynccontextmanager
    async def _intercept(
        self, method: Callback, url: str | URL, *args: Any, **kwargs: Dict[str, Any]
    ) -> AsyncGenerator[aiohttp.ClientResponse]:
        kwargs["headers"] = kwargs.pop("headers", {}) | self._HEADERS
        async with method(url, *args, **kwargs) as response:
            self._called_urls.append(
                (response.status, str(redact_url(response.request_info.url)))
            )
            yield response
