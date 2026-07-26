"""
Scenario 3: OrangeHRM — Admin Login, Create Employee, Search, Update, Delete.

Uses UserDataBuilder for unique names each run (avoids collisions when the
same suite runs repeatedly against a shared demo instance).
"""

from __future__ import annotations

import pytest

from src.data.data_builders import UserDataBuilder
from src.pages.orangehrm.login_page import OrangeHRMLoginPage
from src.pages.orangehrm.pim_page import PIMEmployeeListPage


@pytest.fixture
def orangehrm_page(page, app_config):
    """Logs into OrangeHRM once per test; scenario-specific fixture layered
    on top of the generic `page` fixture."""
    login = OrangeHRMLoginPage(page).open()
    login.login(app_config.app_username or "Admin", app_config.app_password or "admin123")
    return page


@pytest.mark.regression
@pytest.mark.ui
def test_full_employee_lifecycle(orangehrm_page):
    employee = UserDataBuilder().build()

    # Create
    employee_list = PIMEmployeeListPage(orangehrm_page).open()
    add_page = employee_list.click_add()
    toast = add_page.create_employee(employee.first_name, employee.last_name)
    assert "success" in toast.lower()

    # Search
    employee_list = PIMEmployeeListPage(orangehrm_page).open()
    employee_list.search_by_name(f"{employee.first_name} {employee.last_name}")
    assert employee_list.result_count() >= 1

    # Update
    details_page = employee_list.open_first_result()
    updated_last_name = f"{employee.last_name}Updated"
    toast = details_page.update_last_name(updated_last_name)
    assert "success" in toast.lower()

    # Delete
    employee_list = PIMEmployeeListPage(orangehrm_page).open()
    employee_list.search_by_name(f"{employee.first_name} {updated_last_name}")
    toast = employee_list.select_first_result_and_delete()
    assert "success" in toast.lower()
