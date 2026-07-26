"""
OrangeHRM PIM (Personnel Information Management) page — Scenario 3.

Covers: Create Employee, Search Employee, Update Employee, Delete Employee.
Demonstrates handling a real-world SPA with dynamic loading states
(`.oxd-loading-spinner`), toast confirmations, and modal-based deletion
confirmation — all common friction points in production HRMS-style apps.
"""

from __future__ import annotations

from src.pages.base.base_page import BasePage


class PIMEmployeeListPage(BasePage):
    URL_PATH = "/web/index.php/pim/viewEmployeeList"

    ADD_BUTTON = "button:has-text('Add')"
    EMPLOYEE_NAME_SEARCH = "input[placeholder='Type for hints...']"
    SEARCH_BUTTON = "button[type='submit']"
    RESET_BUTTON = "button:has-text('Reset')"
    TABLE_ROW = ".oxd-table-card"
    ROW_CHECKBOX = ".oxd-table-card .oxd-checkbox-input"
    DELETE_SELECTED_BUTTON = "button:has-text('Delete Selected')"
    CONFIRM_DELETE_BUTTON = ".oxd-button--label-danger"
    TOAST_MESSAGE = ".oxd-toast-content-text"
    LOADING_SPINNER = ".oxd-loading-spinner"

    def open(self) -> "PIMEmployeeListPage":
        self.page.goto(self.URL_PATH)
        self._wait_for_spinner_gone()
        return self

    def _wait_for_spinner_gone(self) -> None:
        # OrangeHRM shows a spinner during its AJAX table refresh; Playwright's
        # auto-wait handles element state but not "has this async fetch settled",
        # so we explicitly wait for the spinner to detach.
        spinner = self.page.locator(self.LOADING_SPINNER)
        if spinner.count() > 0:
            spinner.first.wait_for(state="detached", timeout=10000)

    def click_add(self) -> "AddEmployeePage":
        self.click(self.ADD_BUTTON)
        return AddEmployeePage(self.page)

    def search_by_name(self, name: str) -> "PIMEmployeeListPage":
        self.fill(self.EMPLOYEE_NAME_SEARCH, name)
        # OrangeHRM's autocomplete dropdown must be dismissed/selected before submit
        self.page.keyboard.press("Escape")
        self.click(self.SEARCH_BUTTON)
        self._wait_for_spinner_gone()
        return self

    def result_count(self) -> int:
        return self.page.locator(self.TABLE_ROW).count()

    def open_first_result(self) -> "EmployeePersonalDetailsPage":
        self.page.locator(self.TABLE_ROW).first.click()
        return EmployeePersonalDetailsPage(self.page)

    def select_first_result_and_delete(self) -> str:
        self.page.locator(self.ROW_CHECKBOX).first.check()
        self.click(self.DELETE_SELECTED_BUTTON)
        self.click(self.CONFIRM_DELETE_BUTTON)
        return self.text_of(self.TOAST_MESSAGE)


class AddEmployeePage(BasePage):
    FIRST_NAME_INPUT = "input[name='firstName']"
    LAST_NAME_INPUT = "input[name='lastName']"
    EMPLOYEE_ID_INPUT = ".oxd-input-group:has-text('Employee Id') input"
    SAVE_BUTTON = "button[type='submit']"
    TOAST_MESSAGE = ".oxd-toast-content-text"

    def create_employee(self, first_name: str, last_name: str) -> str:
        self.fill(self.FIRST_NAME_INPUT, first_name)
        self.fill(self.LAST_NAME_INPUT, last_name)
        self.click(self.SAVE_BUTTON)
        return self.text_of(self.TOAST_MESSAGE)


class EmployeePersonalDetailsPage(BasePage):
    FIRST_NAME_INPUT = "input[name='firstName']"
    LAST_NAME_INPUT = "input[name='lastName']"
    SAVE_BUTTON = "button[type='submit']"
    TOAST_MESSAGE = ".oxd-toast-content-text"

    def update_last_name(self, new_last_name: str) -> str:
        self.page.locator(self.LAST_NAME_INPUT).fill("")
        self.fill(self.LAST_NAME_INPUT, new_last_name)
        self.click(self.SAVE_BUTTON)
        return self.text_of(self.TOAST_MESSAGE)
