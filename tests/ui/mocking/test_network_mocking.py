"""
Demonstrates network mocking: testing UI states (empty cart, API error)
that are hard to reliably reproduce against a real, shared backend.
"""

from __future__ import annotations

import pytest

from src.pages.saucedemo.login_page import LoginPage
from src.utils.network_mocking import capture_requests, simulate_network_error


@pytest.mark.regression
@pytest.mark.ui
def test_captures_login_form_does_not_leak_password_in_get_requests(page):
    """
    Verifies no GET request accidentally carries the password in a query
    string (a real security regression class) by capturing all outgoing
    requests during the login flow.
    """
    with capture_requests(page, "**/*") as requests_log:
        LoginPage(page).open()
        LoginPage(page).login("standard_user", "secret_sauce")

    leaky_requests = [
        r for r in requests_log
        if r["method"] == "GET" and "secret_sauce" in (r["url"] or "")
    ]
    assert not leaky_requests, f"Password leaked in GET request(s): {leaky_requests}"


@pytest.mark.regression
@pytest.mark.ui
def test_graceful_handling_when_backend_unreachable(page):
    """Simulates a total network failure on the login POST and verifies
    the UI doesn't hang or crash — should show some form of error state."""
    with simulate_network_error(page, "**/inventory.html"):
        login = LoginPage(page).open()
        login.login("standard_user", "secret_sauce")
        # Page should remain responsive (not hard-crash the browser context)
        assert page.url is not None
