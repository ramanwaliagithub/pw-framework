"""
Accessibility Testing utility.

Wraps axe-core (industry-standard a11y engine, also used by Lighthouse and
Deque's own tooling) via axe-playwright-python. Kept as a thin, reusable
helper — not duplicated axe-run boilerplate in every a11y test — with an
explicit severity filter, because failing a build on every 'minor' axe
finding tends to make teams disable a11y testing entirely within a month.
"""

from __future__ import annotations

from typing import Literal

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page

from src.core.logger import get_logger

logger = get_logger(__name__)

Severity = Literal["minor", "moderate", "serious", "critical"]

_SEVERITY_ORDER = {"minor": 0, "moderate": 1, "serious": 2, "critical": 3}


class AccessibilityChecker:
    def __init__(self, page: Page) -> None:
        self._page = page
        self._axe = Axe()

    def scan(self, fail_on_severity: Severity = "serious") -> dict:
        """
        Runs a full-page axe scan. Returns the raw axe results dict for
        reporting, and raises AssertionError if any violation meets or
        exceeds `fail_on_severity` — so a 'minor' contrast nit doesn't
        block a PR the way a missing form label (serious/critical) should.
        """
        results = self._axe.run(self._page)
        violations = results.response.get("violations", [])

        blocking = [
            v for v in violations
            if _SEVERITY_ORDER.get(v.get("impact", "minor"), 0) >= _SEVERITY_ORDER[fail_on_severity]
        ]

        if blocking:
            summary = "\n".join(
                f"  [{v['impact']}] {v['id']}: {v['description']} ({len(v['nodes'])} nodes)"
                for v in blocking
            )
            logger.error("Accessibility violations found:\n%s", summary)
            raise AssertionError(
                f"{len(blocking)} accessibility violation(s) at or above '{fail_on_severity}':\n{summary}"
            )

        if violations:
            logger.warning(
                "%d sub-threshold a11y violations found (below '%s') — logged, not failing build",
                len(violations),
                fail_on_severity,
            )

        return results.response
