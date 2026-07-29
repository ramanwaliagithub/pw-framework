"""
Network Mocking / Request Interception utility.

Wraps Playwright's `page.route()` — lets tests run against a real UI while
stubbing specific backend calls: simulate a 500 error the real backend
rarely produces, force a slow/timeout response to test loading states, or
isolate a UI test from a flaky/rate-limited third-party API entirely.

Design choice: mocks are registered per-test via context manager, so route
handlers are automatically unregistered at test end — a stale mock from
test A can't silently affect test B (shared-context leakage is a classic
flaky-suite root cause).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

from playwright.sync_api import Page, Route

from src.core.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def mock_json_response(
    page: Page,
    url_pattern: str,
    json_body: Any,
    status: int = 200,
) -> Generator[None, None, None]:
    """
    Usage:
        with mock_json_response(page, "**/api/products", {"items": []}):
            page.goto("/products")
            # UI now renders the empty-state, without needing a real
            # backend that returns an empty product list on demand
    """

    def handler(route: Route) -> None:
        logger.info("Intercepted %s -> mocked %d response", route.request.url, status)
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(json_body),
        )

    page.route(url_pattern, handler)
    try:
        yield
    finally:
        page.unroute(url_pattern, handler)


@contextmanager
def simulate_network_error(page: Page, url_pattern: str) -> Generator[None, None, None]:
    """Abort matching requests entirely — simulates offline/DNS failure/CORS block."""

    def handler(route: Route) -> None:
        logger.info("Aborting request to simulate network failure: %s", route.request.url)
        route.abort("failed")

    page.route(url_pattern, handler)
    try:
        yield
    finally:
        page.unroute(url_pattern, handler)


@contextmanager
def delay_response(page: Page, url_pattern: str, delay_ms: int) -> Generator[None, None, None]:
    """Delay matching requests — useful for testing loading spinners/skeletons."""
    import time

    def handler(route: Route) -> None:
        time.sleep(delay_ms / 1000)
        route.continue_()

    page.route(url_pattern, handler)
    try:
        yield
    finally:
        page.unroute(url_pattern, handler)


@contextmanager
def capture_requests(page: Page, url_pattern: str) -> Generator[list[dict], None, None]:
    """
    Records every matching outgoing request (method, url, post_data) without
    altering behavior — useful for asserting the UI called the right API
    with the right payload, without a full backend-response mock.
    """
    captured: list[dict] = []

    def handler(route: Route) -> None:
        captured.append(
            {
                "method": route.request.method,
                "url": route.request.url,
                "post_data": route.request.post_data,
            }
        )
        route.continue_()

    page.route(url_pattern, handler)
    try:
        yield captured
    finally:
        page.unroute(url_pattern, handler)
