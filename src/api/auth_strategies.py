"""
Authentication Strategies for the API layer.

Design pattern: Strategy — the APIClient doesn't know or care whether it's
using Bearer, Basic, OAuth2 client-credentials, or a raw session cookie. It
just calls strategy.apply_headers(). Swapping auth for a test (or across
environments where auth mechanisms differ) means passing a different
strategy object, not branching inside the client.
"""

from __future__ import annotations

import base64
import time
from abc import ABC, abstractmethod

import requests

from src.core.logger import get_logger

logger = get_logger(__name__)


class AuthStrategy(ABC):
    @abstractmethod
    def apply_headers(self) -> dict[str, str]:
        """Return headers to merge into every request."""


class NoAuth(AuthStrategy):
    def apply_headers(self) -> dict[str, str]:
        return {}


class BearerTokenAuth(AuthStrategy):
    def __init__(self, token: str) -> None:
        self._token = token

    def apply_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


class BasicAuth(AuthStrategy):
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply_headers(self) -> dict[str, str]:
        raw = f"{self._username}:{self._password}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}


class OAuth2ClientCredentialsAuth(AuthStrategy):
    """
    Fetches and caches a token via the client-credentials grant, refreshing
    only when expired — avoids hammering the token endpoint once per test
    across a 10k-test suite.
    """

    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str = "") -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._cached_token: str | None = None
        self._expires_at: float = 0.0

    def apply_headers(self) -> dict[str, str]:
        if not self._cached_token or time.time() >= self._expires_at:
            self._refresh()
        return {"Authorization": f"Bearer {self._cached_token}"}

    def _refresh(self) -> None:
        logger.info("Refreshing OAuth2 client-credentials token")
        response = requests.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        self._cached_token = body["access_token"]
        # refresh 30s early to avoid edge-of-expiry race conditions
        self._expires_at = time.time() + int(body.get("expires_in", 3600)) - 30


class SessionCookieAuth(AuthStrategy):
    def __init__(self, cookie_name: str, cookie_value: str) -> None:
        self._cookie_name = cookie_name
        self._cookie_value = cookie_value

    def apply_headers(self) -> dict[str, str]:
        return {"Cookie": f"{self._cookie_name}={self._cookie_value}"}
