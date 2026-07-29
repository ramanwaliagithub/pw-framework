import pytest

from src.pages.saucedemo.login_page import LoginPage
from src.utils.performance_metrics import capture_performance_metrics, collect_console_errors


@pytest.mark.regression
@pytest.mark.ui
def test_login_page_performance_and_console_errors(page):
    errors = collect_console_errors(page)  # must attach before navigation
    LoginPage(page).open()

    metrics = capture_performance_metrics(page)
    metrics.assert_ttfb_under(2000).assert_fcp_under(3000)

    assert not errors, f"Console errors detected on login page: {errors}"
