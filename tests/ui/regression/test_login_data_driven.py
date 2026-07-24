"""
Data-driven regression test: login outcomes sourced from JSON, decoupling
test data from test code so a business analyst / QA lead can update
credentials-under-test without touching Python.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.data.data_loaders import load_test_data
from src.pages.saucedemo.login_page import LoginPage
from src.pages.saucedemo.inventory_page import InventoryPage

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "json" / "login_credentials.json"
_CASES = load_test_data(_DATA_PATH)


@pytest.mark.regression
@pytest.mark.ui
@pytest.mark.parametrize("case", _CASES, ids=[c["username"] or "empty" for c in _CASES])
def test_login_outcomes(page, case):
    login = LoginPage(page).open()
    login.login(case["username"], case["password"])

    if case["expected"] == "success":
        assert InventoryPage(page).is_loaded()
    elif case["expected"] == "locked_out":
        assert login.is_error_displayed()
        assert "locked out" in login.get_error_message().lower()
