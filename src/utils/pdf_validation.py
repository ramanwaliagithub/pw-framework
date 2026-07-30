"""
PDF Validation utility.

Used for downloaded artifacts (bank statements, invoices, receipts) where
the test needs to assert on actual document content, not just "a file
exists". Kept intentionally minimal (text extraction + substring/regex
checks) — full layout/visual PDF diffing is a separate, heavier tool if
ever needed.
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


def extract_text(pdf_path: str | Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def assert_pdf_contains(pdf_path: str | Path, expected_substring: str) -> None:
    text = extract_text(pdf_path)
    assert expected_substring in text, (
        f"Expected substring '{expected_substring}' not found in PDF {pdf_path}"
    )


def assert_pdf_matches_pattern(pdf_path: str | Path, pattern: str) -> re.Match:
    text = extract_text(pdf_path)
    match = re.search(pattern, text)
    assert match, f"Pattern '{pattern}' not found in PDF {pdf_path}"
    return match


def page_count(pdf_path: str | Path) -> int:
    return len(PdfReader(str(pdf_path)).pages)
