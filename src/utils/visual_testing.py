"""
Visual Testing utility.

IMPORTANT: Playwright's built-in `expect(page).to_have_screenshot()` only
works under Playwright's own JS/TS test runner (or newer pytest-playwright
snapshot fixtures in restricted setups) — it is NOT generally available
against a plain `Page` object from `sync_playwright()` the way this
framework uses Playwright. Reaching for it here would have been a
plausible-looking but broken API call.

Instead this module implements a small, portable Pillow-based pixel diff:
capture -> compare against a stored baseline -> compute diff ratio -> pass
a highlighted diff image to the report on failure. This works with any
pytest + Playwright sync_api setup, verified against real screenshots.

Baseline workflow: run with `update_baseline=True` once after an
intentional UI change (commit the new baseline in the same PR as the code
change, so reviewers see both), then leave it False for normal CI runs.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Page

from src.core.logger import get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_DIR = _REPO_ROOT / "tests" / "visual_baselines"
_DIFF_DIR = _REPO_ROOT / "reports" / "visual_diffs"
_BASELINE_DIR.mkdir(parents=True, exist_ok=True)
_DIFF_DIR.mkdir(parents=True, exist_ok=True)


class VisualMismatchError(AssertionError):
    pass


def assert_matches_baseline(
    page: Page,
    snapshot_name: str,
    max_diff_ratio: float = 0.01,
    full_page: bool = True,
    update_baseline: bool = False,
) -> None:
    """
    Compares current page render against a stored baseline PNG.

    max_diff_ratio=0.01 tolerates ~1% pixel diff — accounts for
    anti-aliasing/font-rendering variance across CI runners without
    masking real visual regressions.
    """
    baseline_path = _BASELINE_DIR / f"{snapshot_name}.png"
    current_path = _DIFF_DIR / f"{snapshot_name}_current.png"

    page.screenshot(path=str(current_path), full_page=full_page)

    if update_baseline or not baseline_path.exists():
        baseline_path.write_bytes(current_path.read_bytes())
        logger.info("Baseline %s written/updated at %s", snapshot_name, baseline_path)
        return

    baseline_img = Image.open(baseline_path).convert("RGB")
    current_img = Image.open(current_path).convert("RGB")

    if baseline_img.size != current_img.size:
        raise VisualMismatchError(
            f"Size mismatch for '{snapshot_name}': "
            f"baseline={baseline_img.size} vs current={current_img.size}"
        )

    diff = ImageChops.difference(baseline_img, current_img)
    # getbbox() returns None if every pixel is identical (fast path, no full scan needed);
    # otherwise fall back to a bounding-box-scoped pixel count for the diff ratio.
    bbox = diff.getbbox()
    total_pixels = baseline_img.size[0] * baseline_img.size[1]
    if bbox is None:
        diff_ratio = 0.0
    else:
        diff_region = diff.crop(bbox)
        diff_pixels = sum(
            1 for px in diff_region.getdata() if px != (0, 0, 0)  # noqa: PLR2004 (Pillow tuple compare)
        )
        diff_ratio = diff_pixels / total_pixels

    if diff_ratio > max_diff_ratio:
        diff_path = _DIFF_DIR / f"{snapshot_name}_diff.png"
        diff.save(diff_path)
        raise VisualMismatchError(
            f"Visual mismatch for '{snapshot_name}': {diff_ratio:.2%} pixels differ "
            f"(threshold {max_diff_ratio:.2%}). Diff image: {diff_path}"
        )

    logger.debug("Visual check passed for '%s': %.4f%% diff", snapshot_name, diff_ratio * 100)
