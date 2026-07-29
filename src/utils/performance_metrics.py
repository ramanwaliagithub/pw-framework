"""
Performance Metrics utility.

Pulls real browser performance data via the standard Navigation Timing
Level 2 and Paint Timing APIs (window.performance) — the same data
Lighthouse/Chrome DevTools surface — rather than approximating timing in
Python with wall-clock measurements around page.goto(), which would
include Playwright/network overhead not representative of real user
experience.
"""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

from src.core.logger import get_logger

logger = get_logger(__name__)

_PERF_SCRIPT = """
() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint');
    const fcp = paint.find(p => p.name === 'first-contentful-paint');
    return {
        dns_ms: nav ? (nav.domainLookupEnd - nav.domainLookupStart) : null,
        tcp_ms: nav ? (nav.connectEnd - nav.connectStart) : null,
        ttfb_ms: nav ? (nav.responseStart - nav.requestStart) : null,
        dom_content_loaded_ms: nav ? nav.domContentLoadedEventEnd : null,
        load_event_ms: nav ? nav.loadEventEnd : null,
        first_contentful_paint_ms: fcp ? fcp.startTime : null,
        transfer_size_bytes: nav ? nav.transferSize : null
    };
}
"""


@dataclass
class PerformanceMetrics:
    dns_ms: float | None
    tcp_ms: float | None
    ttfb_ms: float | None
    dom_content_loaded_ms: float | None
    load_event_ms: float | None
    first_contentful_paint_ms: float | None
    transfer_size_bytes: float | None

    def assert_ttfb_under(self, max_ms: float) -> "PerformanceMetrics":
        assert self.ttfb_ms is not None and self.ttfb_ms <= max_ms, (
            f"TTFB {self.ttfb_ms}ms exceeded threshold {max_ms}ms"
        )
        return self

    def assert_fcp_under(self, max_ms: float) -> "PerformanceMetrics":
        assert self.first_contentful_paint_ms is not None and self.first_contentful_paint_ms <= max_ms, (
            f"FCP {self.first_contentful_paint_ms}ms exceeded threshold {max_ms}ms"
        )
        return self


def capture_performance_metrics(page: Page) -> PerformanceMetrics:
    raw = page.evaluate(_PERF_SCRIPT)
    logger.info("Performance metrics: %s", raw)
    return PerformanceMetrics(**raw)


def collect_console_errors(page: Page) -> list[str]:
    """
    Attach BEFORE navigation. Returns a list that fills as console errors
    occur — pass this list into an assertion after the test flow completes.
    """
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors
