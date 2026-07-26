"""
Scenario 4: Banking — Transfer Funds, Validate Balance, Download Statement.

Demonstrates: cross-layer verification (UI action -> DB assertion, not just
UI-visible balance), file download handling via BasePage.wait_for_download,
and PDF statement validation (see pdf_validation.py in this chapter).
"""

from __future__ import annotations

from src.pages.base.base_page import BasePage


class DashboardPage(BasePage):
    ACCOUNT_BALANCE = "[data-test='account-balance']"
    TRANSFER_FUNDS_LINK = "a:has-text('Transfer Funds')"
    STATEMENTS_LINK = "a:has-text('Statements')"

    def get_balance(self) -> float:
        text = self.text_of(self.ACCOUNT_BALANCE)  # e.g. "$4,582.10"
        return float(text.replace("$", "").replace(",", "").strip())

    def go_to_transfer_funds(self) -> "TransferFundsPage":
        self.click(self.TRANSFER_FUNDS_LINK)
        return TransferFundsPage(self.page)

    def go_to_statements(self) -> "StatementsPage":
        self.click(self.STATEMENTS_LINK)
        return StatementsPage(self.page)


class TransferFundsPage(BasePage):
    FROM_ACCOUNT_SELECT = "select[name='fromAccount']"
    TO_ACCOUNT_SELECT = "select[name='toAccount']"
    AMOUNT_INPUT = "input[name='amount']"
    SUBMIT_BUTTON = "button[type='submit']"
    CONFIRMATION_MESSAGE = "[data-test='transfer-confirmation']"

    def transfer(self, from_account: str, to_account: str, amount: float) -> str:
        self.select_option(self.FROM_ACCOUNT_SELECT, from_account)
        self.select_option(self.TO_ACCOUNT_SELECT, to_account)
        self.fill(self.AMOUNT_INPUT, str(amount))
        self.click(self.SUBMIT_BUTTON)
        return self.text_of(self.CONFIRMATION_MESSAGE)


class StatementsPage(BasePage):
    DOWNLOAD_BUTTON = "button:has-text('Download Statement')"

    def download_statement(self, save_dir: str) -> str:
        return self.wait_for_download(self.DOWNLOAD_BUTTON, save_dir)
