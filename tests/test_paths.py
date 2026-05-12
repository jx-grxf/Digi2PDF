from __future__ import annotations

from digi2pdf.paths import MAX_FILENAME_LENGTH, safe_filename


def test_safe_filename_guards_windows_reserved_names() -> None:
    assert safe_filename("CON") == "CON-book"
    assert safe_filename("nul.txt") == "nul.txt-book"


def test_safe_filename_limits_long_names() -> None:
    name = safe_filename("a" * 200)

    assert len(name) == MAX_FILENAME_LENGTH


def test_safe_filename_replaces_separators() -> None:
    assert safe_filename("Math/Book\\2026") == "Math_Book_2026"
