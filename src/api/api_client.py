"""
API Client.

Design pattern: Facade + Strategy (auth). Wraps Playwright's
APIRequestContext (not `requests`) so API tests share the same tracing,
proxy config, and network stack as UI tests — important when a scenario
mixes API setup with UI verification in one trace.zip.

Schema validation is intentionally a separate explicit step
(`validate_schema`), not automatic on every call, because not every
response body needs strict-schema enforcement (e.g. paginated list
responses vs a single resource).
"""

from __future__ import annotations

from typing import Any

import jsonschema
from playwright.sync_api import APIRequestContext, APIResponse, Playwright

from src.api.auth_strategies import AuthStrategy, NoAuth
from src.core.logger import get_logger

logger = get_logger(__name__)

_SENSITIVE_HEADER_KEYS = {"authorization", "cookie", "x-api-key"}


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: ("***MASKED***" if k.lower() in _SENSITIVE_HEADER_KEYS else v)
        for k, v in headers.items()
    }


class APIResponseWrapper:
    """Thin wrapper adding fluent assertion helpers on top of Playwright's APIResponse."""

    def __init__(self, response: APIResponse) -> None:
        self.raw = response
        self.status = response.status
        self.ok = response.ok
        self._json_cache: Any = None

    def json(self) -> Any:
        if self._json_cache is None:
            self._json_cache = self.raw.json()
        return self._json_cache

    def expect_status(self, expected: int) -> "APIResponseWrapper":
        assert self.status == expected, (
            f"Expected status {expected}, got {self.status}. Body: {self.raw.text()[:500]}"
        )
        return self

    def expect_ok(self) -> "APIResponseWrapper":
        assert self.ok, f"Expected 2xx, got {self.status}. Body: {self.raw.text()[:500]}"
        return self

    def validate_schema(self, schema: dict) -> "APIResponseWrapper":
        jsonschema.validate(instance=self.json(), schema=schema)
        return self


class APIClient:
    def __init__(
        self,
        playwright: Playwright,
        base_url: str,
        auth: AuthStrategy | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._auth = auth or NoAuth()
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        self._context: APIRequestContext = playwright.request.new_context(
            base_url=base_url,
            extra_http_headers=headers,
        )

    def _merged_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        return {**self._auth.apply_headers(), **(extra or {})}

    def _log_request(self, method: str, url: str, headers: dict[str, str]) -> None:
        logger.info("API %s %s | headers=%s", method, url, _safe_headers(headers))

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> APIResponseWrapper:
        merged = self._merged_headers(headers)
        self._log_request("GET", url, merged)
        resp = self._context.get(url, params=params, headers=merged)
        return APIResponseWrapper(resp)

    def post(self, url: str, data: dict | None = None, headers: dict | None = None) -> APIResponseWrapper:
        merged = self._merged_headers(headers)
        self._log_request("POST", url, merged)
        resp = self._context.post(url, data=data, headers=merged)
        return APIResponseWrapper(resp)

    def put(self, url: str, data: dict | None = None, headers: dict | None = None) -> APIResponseWrapper:
        merged = self._merged_headers(headers)
        self._log_request("PUT", url, merged)
        resp = self._context.put(url, data=data, headers=merged)
        return APIResponseWrapper(resp)

    def patch(self, url: str, data: dict | None = None, headers: dict | None = None) -> APIResponseWrapper:
        merged = self._merged_headers(headers)
        self._log_request("PATCH", url, merged)
        resp = self._context.patch(url, data=data, headers=merged)
        return APIResponseWrapper(resp)

    def delete(self, url: str, headers: dict | None = None) -> APIResponseWrapper:
        merged = self._merged_headers(headers)
        self._log_request("DELETE", url, merged)
        resp = self._context.delete(url, headers=merged)
        return APIResponseWrapper(resp)

    def dispose(self) -> None:
        self._context.dispose()
