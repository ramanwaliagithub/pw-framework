"""
Smoke test: SauceDemo login.

Demonstrates: fixture injection, page object usage, custom markers,
parameterization for negative-path data-driven testing.
"""

from __future__ import annotations

import pytest

from src.pages.saucedemo.login_page import LoginPage
from src.pages.saucedemo.inventory_page import InventoryPage


@pytest.mark.smoke
@pytest.mark.ui
def test_valid_login_lands_on_inventory(page, app_config):
    login = LoginPage(page).open()
    login.login(app_config.app_username, app_config.app_password)

    inventory = InventoryPage(page)
    assert inventory.is_loaded(), "Inventory page did not load after valid login"


@pytest.mark.smoke
@pytest.mark.ui
@pytest.mark.parametrize(
    "username,password,expected_error_substring",
    [
        ("locked_out_user", "secret_sauce", "locked out"),
        ("standard_user", "wrong_password", "do not match"),
        ("", "", "Username is required"),
    ],
    ids=["locked-out-user", "wrong-password", "empty-credentials"],
)
def test_invalid_login_shows_error(page, username, password, expected_error_substring):
    login = LoginPage(page).open()
    login.login(username, password)

    assert login.is_error_displayed()
    assert expected_error_substring.lower() in login.get_error_message().lower()
