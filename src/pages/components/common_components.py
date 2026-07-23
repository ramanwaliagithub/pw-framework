"""
Reusable Components.

Design pattern: Composition over inheritance. A page object HAS-A
SortDropdown/CartBadge rather than every page reimplementing dropdown logic.
Components take a Playwright Page + root selector; they know nothing about
which page they're embedded in, so the same component class works on any
page that happens to contain that widget.
"""

from __future__ import annotations

from playwright.sync_api import Page

from src.core.logger import get_logger

logger = get_logger(__name__)


class SortDropdown:
    """Generic <select>-based sort control, e.g. SauceDemo's product sort."""

    def __init__(self, page: Page, selector: str) -> None:
        self.page = page
        self.selector = selector

    def sort_by(self, value: str) -> None:
        logger.debug("Sorting via %s -> %s", self.selector, value)
        self.page.locator(self.selector).select_option(value)

    def current_value(self) -> str:
        return self.page.locator(self.selector).input_value()


class CartBadge:
    """Shopping cart icon + item-count badge, reused across product/cart/checkout pages."""

    def __init__(self, page: Page, badge_selector: str, icon_selector: str) -> None:
        self.page = page
        self.badge_selector = badge_selector
        self.icon_selector = icon_selector

    def item_count(self) -> int:
        locator = self.page.locator(self.badge_selector)
        if locator.count() == 0:
            return 0
        return int(locator.first.inner_text().strip())

    def open(self) -> None:
        self.page.locator(self.icon_selector).click()
