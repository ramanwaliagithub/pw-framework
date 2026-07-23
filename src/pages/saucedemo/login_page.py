from __future__ import annotations

from src.pages.base.base_page import BasePage


class LoginPage(BasePage):
    URL_PATH = "/"

    USERNAME_INPUT = "#user-name"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#login-button"
    ERROR_MESSAGE = "[data-test='error']"

    def open(self) -> "LoginPage":
        self.page.goto(self.URL_PATH)
        return self

    def enter_username(self, username: str) -> "LoginPage":
        self.fill(self.USERNAME_INPUT, username)
        return self

    def enter_password(self, password: str) -> "LoginPage":
        self.fill(self.PASSWORD_INPUT, password)
        return self

    def click_login(self) -> "LoginPage":
        self.click(self.LOGIN_BUTTON)
        return self

    def login(self, username: str, password: str) -> "LoginPage":
        """Fluent convenience wrapping the three steps above."""
        return self.enter_username(username).enter_password(password).click_login()

    def get_error_message(self) -> str:
        return self.text_of(self.ERROR_MESSAGE)

    def is_error_displayed(self) -> bool:
        return self.is_visible(self.ERROR_MESSAGE, timeout_ms=2000)
