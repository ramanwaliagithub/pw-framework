from __future__ import annotations

from src.pages.base.base_page import BasePage


class OrangeHRMLoginPage(BasePage):
    URL_PATH = "/web/index.php/auth/login"

    USERNAME_INPUT = "input[name='username']"
    PASSWORD_INPUT = "input[name='password']"
    LOGIN_BUTTON = "button[type='submit']"
    ERROR_ALERT = ".oxd-alert-content-text"

    def open(self) -> "OrangeHRMLoginPage":
        self.page.goto(self.URL_PATH)
        return self

    def login(self, username: str, password: str) -> "OrangeHRMLoginPage":
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)
        return self

    def get_error_text(self) -> str:
        return self.text_of(self.ERROR_ALERT)
