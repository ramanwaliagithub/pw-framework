"""
Playwright Manager.

Design pattern: Facade — hides Playwright's multi-step lifecycle
(start playwright -> launch browser -> new context -> new page -> tracing
start/stop -> context close -> browser close -> playwright stop) behind a
handful of simple methods. Tests and fixtures never touch the raw
Playwright API directly; they go through this class.

Also owns:
- Storage-state based session reuse (login once, reuse cookies/localStorage
  across many tests to cut suite runtime dramatically)
- Per-test tracing, so every failed test gets a trace.zip without every
  test paying the recording overhead unconditionally (trace is started
  always but only *saved* on failure, decided by the fixture layer)
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from src.core.browser_factory import BrowserFactory
from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STORAGE_STATE_DIR = _REPO_ROOT / ".auth"
_STORAGE_STATE_DIR.mkdir(exist_ok=True)


class PlaywrightManager:
    """One instance per test (see fixtures.py) — not a singleton.

    Singleton would be wrong here: xdist runs many tests in parallel worker
    processes, and even within one process each test needs an isolated
    BrowserContext so cookies/localStorage/network state from test A never
    leak into test B (test isolation requirement).
    """
    
    def __init__(self, config: Config) -> None:
        self._config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._tracing_started = False

    # -- lifecycle -----------------------------------------------------

    def start(self, storage_state_path: str | None = None) -> Page:
        self._playwright = sync_playwright().start()
        self._browser = BrowserFactory.create(self._playwright, self._config)

        context_kwargs: dict = {
            "viewport": self._config.viewport,
            "base_url": self._config.base_url or None,
            "accept_downloads": True,
        }
        if self._config.video_on_failure:
            context_kwargs["record_video_dir"] = str(_REPO_ROOT / "reports" / "videos")

        if storage_state_path and Path(storage_state_path).exists():
            context_kwargs["storage_state"] = storage_state_path
            logger.info("Reusing storage state from %s", storage_state_path)

        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self._config.timeout_ms)
        self._context.set_default_navigation_timeout(self._config.navigation_timeout_ms)

        if self._config.trace_on_failure:
            self._context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self._tracing_started = True

        self._page = self._context.new_page()
        return self._page

    def save_storage_state(self, name: str) -> str:
        """Persist current context's cookies/localStorage for reuse (login-once pattern)."""
        if not self._context:
            raise RuntimeError("Context not started")
        path = _STORAGE_STATE_DIR / f"{name}.json"
        self._context.storage_state(path=str(path))
        logger.info("Saved storage state to %s", path)
        return str(path)

    def stop(self, test_failed: bool, test_name: str) -> dict[str, str | None]:
        """Tear down and, on failure, persist trace/screenshot artifacts.

        Returns dict of artifact paths (may contain None) for the reporting
        layer to attach to Allure/HTML reports.
        """
        artifacts: dict[str, str | None] = {"trace": None, "screenshot": None, "video": None}

        try:
            if self._page and test_failed and self._config.screenshot_on_failure:
                shot_path = _REPO_ROOT / "reports" / "screenshots" / f"{test_name}.png"
                shot_path.parent.mkdir(parents=True, exist_ok=True)
                self._page.screenshot(path=str(shot_path), full_page=True)
                artifacts["screenshot"] = str(shot_path)
                logger.info("Captured failure screenshot: %s", shot_path)

            if self._context and self._tracing_started:
                if test_failed:
                    trace_path = _REPO_ROOT / "reports" / "traces" / f"{test_name}.zip"
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    self._context.tracing.stop(path=str(trace_path))
                    artifacts["trace"] = str(trace_path)
                    logger.info("Saved trace: %s", trace_path)
                else:
                    self._context.tracing.stop()

            if self._page and self._page.video and test_failed:
                artifacts["video"] = self._page.video.path()

        finally:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()

        return artifacts

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Page not started — call start() first")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Context not started — call start() first")
        return self._context
