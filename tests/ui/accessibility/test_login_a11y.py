import pytest

from src.pages.saucedemo.login_page import LoginPage
from src.utils.accessibility import AccessibilityChecker


@pytest.mark.accessibility
@pytest.mark.regression
def test_login_page_has_no_serious_a11y_violations(page):
    LoginPage(page).open()
    AccessibilityChecker(page).scan(fail_on_severity="serious")
