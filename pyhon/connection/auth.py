import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple

import aiohttp
from aiohttp import ClientResponse

from pyhon import const, exceptions
from pyhon.connection.device import HonDevice
from pyhon.connection.handler.auth import HonAuthConnectionHandler

_LOGGER = logging.getLogger(__name__)


@dataclass
class HonAuthData:
    access_token: str = ""
    refresh_token: str = ""
    cognito_token: str = ""
    id_token: str = ""


class HonAuth:
    _TOKEN_EXPIRES_AFTER_HOURS = 8
    _TOKEN_EXPIRE_WARNING_HOURS = 7

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        device: HonDevice,
    ) -> None:
        self._session = session
        self._request = HonAuthConnectionHandler(session)
        self._email = email
        self._password = password
        self._device = device
        self._expires: datetime = datetime.utcnow()
        self._auth = HonAuthData()

    @property
    def cognito_token(self) -> str:
        return self._auth.cognito_token

    @property
    def id_token(self) -> str:
        return self._auth.id_token

    @property
    def access_token(self) -> str:
        return self._auth.access_token

    @property
    def refresh_token(self) -> str:
        return self._auth.refresh_token

    def _check_token_expiration(self, hours: int) -> bool:
        return datetime.utcnow() >= self._expires + timedelta(hours=hours)

    @property
    def token_is_expired(self) -> bool:
        return self._check_token_expiration(self._TOKEN_EXPIRES_AFTER_HOURS)

    @property
    def token_expires_soon(self) -> bool:
        return self._check_token_expiration(self._TOKEN_EXPIRE_WARNING_HOURS)

    async def _error_logger(self, response: ClientResponse, fail: bool = True) -> None:
        output = "hOn Authentication Error\n"
        for i, (status, url) in enumerate(self._request.called_urls):
            output += f" {i + 1: 2d}     {status} - {url}\n"
        output += f"ERROR - {response.status} - {response.request_info.url}\n"
        output += f"{15 * '='} Response {15 * '='}\n{await response.text()}\n{40 * '='}"
        _LOGGER.error(output)
        if fail:
            raise exceptions.HonAuthenticationError("Can't login")

    @staticmethod
    def _generate_pkce_pair() -> Tuple[str, str]:
        """Return a (code_verifier, code_challenge) pair for the CIAM PKCE login."""
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
        )
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    async def _get_session_id(self, code_challenge: str) -> str:
        """Submit credentials to /ciam/authorize and return the one-time session id."""
        params = {
            "username": self._email,
            "password": self._password,
            "code_challenge": code_challenge,
        }
        async with self._request.get(
            f"{const.API_URL}/ciam/authorize", params=params
        ) as response:
            if response.status != 200:
                await self._error_logger(response)
                return ""
            session_id: str = (await response.json()).get("session_id", "")
            if not session_id:
                await self._error_logger(response)
            return session_id

    async def _get_tokens(self, session_id: str, code_verifier: str) -> bool:
        """Exchange the session id + PKCE verifier for the auth tokens."""
        async with self._request.post(
            f"{const.API_URL}/ciam/token",
            json={"session_id": session_id, "code_verifier": code_verifier},
        ) as response:
            if response.status != 200:
                await self._error_logger(response)
                return False
            tokens = (await response.json()).get("tokens", {})
            self._auth.id_token = tokens.get("id_token", "")
            self._auth.access_token = tokens.get("access_token", "")
            self._auth.refresh_token = tokens.get("refresh_token", "")
            self._auth.cognito_token = tokens.get("cognito_token", "")
            if not (self._auth.cognito_token and self._auth.id_token):
                await self._error_logger(response)
                return False
        return True

    async def authenticate(self) -> None:
        """Authenticate against the hOn CIAM endpoint.

        Replaces the legacy Salesforce Aura / OAuth2 login that Haier retired
        in 2026-06. The app now logs in through ``/ciam/authorize`` and
        ``/ciam/token`` (PKCE); the old ``/commands/v1/appliance`` listing
        returns an empty list.
        """
        self.clear()
        code_verifier, code_challenge = self._generate_pkce_pair()
        if not (session_id := await self._get_session_id(code_challenge)):
            raise exceptions.HonAuthenticationError("Can't get session id")
        if not await self._get_tokens(session_id, code_verifier):
            raise exceptions.HonAuthenticationError("Can't get api token")
        self._expires = datetime.utcnow()

    async def refresh(self, refresh_token: str = "") -> bool:
        """Refresh the session.

        The CIAM endpoint does not expose a usable refresh-token grant, so a full
        re-authentication is performed with the stored credentials.
        """
        if refresh_token:
            self._auth.refresh_token = refresh_token
        try:
            await self.authenticate()
        except exceptions.HonAuthenticationError:
            return False
        return True

    def clear(self) -> None:
        self._session.cookie_jar.clear_domain(const.AUTH_API.split("/")[-2])
        self._request.called_urls = []
        self._auth.cognito_token = ""
        self._auth.id_token = ""
        self._auth.access_token = ""
        self._auth.refresh_token = ""
