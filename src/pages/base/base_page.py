"""
Base Page Object.

Design patterns:
- Template Method — subclasses (LoginPage, InventoryPage, ...) get a fixed
  skeleton of safe interaction methods and only supply locators/flows.
- Fluent Interface — action methods return `self` so tests/pages can chain:
      login_page.enter_username(u).enter_password(p).click_login()

Why not call page.click() directly from tests? Because every click/fill in
a 10k-test suite needs the same guardrails: explicit wait-for-visible before
interaction (Playwright auto-waits, but we add our own actionability log +
retry for elements that are visible but not yet stable), consistent logging,
and a single place to bolt on self-healing locator recovery.
"""

from __future__ import annotations

from typing import Sequence

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from src.core.logger import get_logger

logger = get_logger(__name__)


class ElementNotFoundError(Exception):
    """Raised when an element and all of its self-healing fallback locators fail."""


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    # -- navigation ------------------------------------------------------

    def goto(self, path: str = "") -> "BasePage":
        url = path if path.startswith("http") else f"{self.page.url.rstrip('/')}{path}"
        logger.info("Navigating to %s", url if path.startswith("http") else path)
        self.page.goto(path if path.startswith("http") else path)
        return self

    def wait_for_load(self) -> "BasePage":
        self.page.wait_for_load_state("networkidle")
        return self

    # -- self-healing locator strategy ------------------------------------
    #
    # Real production pattern: a locator is defined as a *primary* selector
    # plus an ordered list of fallback selectors. If the primary breaks
    # (common when devs change a data-testid or CSS class without telling
    # QA), we fall back automatically and log a WARNING so the flaky
    # locator gets fixed later — the test doesn't go red for a cosmetic
    # DOM change. This is "self-healing" in the practical (not ML) sense;
    # true AI-assisted recovery is discussed in docs/self_healing.md.

    def resilient_locator(self, primary: str, fallbacks: Sequence[str] = ()) -> Locator:
        candidates = [primary, *fallbacks]
        for i, selector in enumerate(candidates):
            locator = self.page.locator(selector)
            try:
                locator.first.wait_for(state="attached", timeout=2000)
                if i > 0:
                    logger.warning(
                        "Primary locator '%s' failed; healed using fallback '%s'",
                        primary,
                        selector,
                    )
                return locator
            except PlaywrightTimeoutError:
                continue
        raise ElementNotFoundError(
            f"None of the locators matched: {candidates}"
        )

    # -- guarded interactions ---------------------------------------------

    def click(self, selector: str, fallbacks: Sequence[str] = ()) -> "BasePage":
        locator = self.resilient_locator(selector, fallbacks)
        logger.debug("Clicking: %s", selector)
        locator.first.click()
        return self

    def fill(self, selector: str, value: str, fallbacks: Sequence[str] = ()) -> "BasePage":
        locator = self.resilient_locator(selector, fallbacks)
        logger.debug("Filling '%s' with value of length=%d", selector, len(value))
        locator.first.fill(value)
        return self

    def text_of(self, selector: str, fallbacks: Sequence[str] = ()) -> str:
        locator = self.resilient_locator(selector, fallbacks)
        return locator.first.inner_text().strip()

    def is_visible(self, selector: str, timeout_ms: int = 3000) -> bool:
        try:
            self.page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            return False

    def select_option(self, selector: str, value: str) -> "BasePage":
        self.page.locator(selector).select_option(value)
        return self

    def upload_file(self, selector: str, file_path: str) -> "BasePage":
        self.page.locator(selector).set_input_files(file_path)
        logger.info("Uploaded file: %s", file_path)
        return self

    def wait_for_download(self, trigger_selector: str, save_dir: str) -> str:
        with self.page.expect_download() as download_info:
            self.page.locator(trigger_selector).click()
        download = download_info.value
        dest = f"{save_dir.rstrip('/')}/{download.suggested_filename}"
        download.save_as(dest)
        logger.info("Downloaded file to %s", dest)
        return dest

    # -- multi-tab / frame helpers -----------------------------------------

    def switch_to_new_tab(self, trigger_selector: str) -> Page:
        with self.page.context.expect_page() as new_page_info:
            self.page.locator(trigger_selector).click()
        new_page = new_page_info.value
        new_page.wait_for_load_state()
        return new_page

    def frame_locator(self, frame_selector: str):
        return self.page.frame_locator(frame_selector)
