"""
Root conftest.py — the wiring layer.

This is where custom CLI options, session/function-scoped fixtures, and
pytest hooks live. Every test in tests/ui/** gets a ready-to-use `page`
fixture without knowing anything about PlaywrightManager, Config, or
tracing — that's the point of the layered architecture: tests stay thin.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Page

from src.core.config import get_config
from src.core.logger import get_logger, new_correlation_id
from src.core.playwright_manager import PlaywrightManager

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Custom CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--env",
        action="store",
        default=None,
        help="Override TEST_ENV (qa|staging|prod) for this run.",
    )
    parser.addoption(
        "--use-storage-state",
        action="store_true",
        default=False,
        help="Reuse saved login session instead of logging in per test.",
    )


def pytest_configure(config: pytest.Config) -> None:
    import os

    env_override = config.getoption("--env")
    if env_override:
        os.environ["TEST_ENV"] = env_override


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_config():
    return get_config(force_reload=True)


@pytest.fixture(scope="function")
def page(request: pytest.FixtureRequest, app_config) -> Generator[Page, None, None]:
    """
    Function-scoped: every test gets its own isolated browser context.
    This is intentional test-isolation, not an oversight — session-scoped
    browser + function-scoped context is a common *optimization* for large
    suites (see docs/scaling.md), but starts here at the safe default.
    """
    new_correlation_id()
    manager = PlaywrightManager(app_config)

    storage_state = None
    if request.config.getoption("--use-storage-state"):
        candidate = _REPO_ROOT / ".auth" / "standard_user.json"
        if candidate.exists():
            storage_state = str(candidate)

    pw_page = manager.start(storage_state_path=storage_state)
    pw_page._manager = manager  # stash for the failure hook below

    yield pw_page

    test_failed = request.node.rep_call.failed if hasattr(request.node, "rep_call") else False
    artifacts = manager.stop(test_failed=test_failed, test_name=request.node.name)

    if test_failed:
        logger.error("Test FAILED: %s | artifacts=%s", request.node.name, artifacts)
        _attach_allure_artifacts(artifacts)


def _attach_allure_artifacts(artifacts: dict) -> None:
    try:
        import allure
    except ImportError:
        return
    if artifacts.get("screenshot"):
        allure.attach.file(
            artifacts["screenshot"], name="screenshot", attachment_type=allure.attachment_type.PNG
        )
    if artifacts.get("trace"):
        allure.attach.file(
            artifacts["trace"], name="trace", attachment_type=allure.attachment_type.ZIP
        )


# ---------------------------------------------------------------------------
# Hooks — capture pass/fail per phase so the `page` fixture teardown above
# knows whether the test body actually failed (request.node.rep_call).
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
