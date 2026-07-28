import pytest

from src.pages.saucedemo.login_page import LoginPage
from src.utils.visual_testing import assert_matches_baseline


@pytest.mark.regression
@pytest.mark.ui
def test_login_page_visual_baseline(page):
    """
    First run (or with update_baseline=True) captures the baseline.
    Subsequent runs diff against it. Kept out of the `smoke` marker
    deliberately — visual diffs need human review, not auto-merge-blocking.
    """
    LoginPage(page).open()
    assert_matches_baseline(page, "saucedemo_login_page", max_diff_ratio=0.01)
