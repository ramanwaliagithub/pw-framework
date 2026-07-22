"""
Browser Factory.

Design pattern: Factory Method — callers ask for "a browser" without
knowing whether that means chromium, firefox, or webkit. Adding a new
browser type later means editing one dict here, not every test file.
"""

from __future__ import annotations

from typing import Callable

from playwright.sync_api import Browser, BrowserType, Playwright

from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger(__name__)


class BrowserFactory:
    _LAUNCHERS: dict[str, Callable[[Playwright], BrowserType]] = {
        "chromium": lambda p: p.chromium,
        "firefox": lambda p: p.firefox,
        "webkit": lambda p: p.webkit,
    }

    @classmethod
    def create(cls, playwright: Playwright, config: Config) -> Browser:
        browser_name = config.browser.lower()
        if browser_name not in cls._LAUNCHERS:
            raise ValueError(
                f"Unsupported browser '{browser_name}'. "
                f"Supported: {list(cls._LAUNCHERS.keys())}"
            )

        browser_type = cls._LAUNCHERS[browser_name](playwright)

        logger.info(
            "Launching browser=%s headless=%s slow_mo=%sms",
            browser_name,
            config.headless,
            config.slow_mo_ms,
        )

        return browser_type.launch(
            headless=config.headless,
            slow_mo=config.slow_mo_ms,
            args=["--start-maximized"] if browser_name == "chromium" else [],
        )
