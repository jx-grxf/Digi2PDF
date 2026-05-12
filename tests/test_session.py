from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from digi2pdf.models import BookChoice, CropBox, OcrProfile, RuntimeOptions
from digi2pdf.session import Digi2PDFSession


class NullSink:
    def start_dashboard(self, *_args: object) -> None:
        return

    def finish_dashboard(self) -> None:
        return

    def warn(self, _message: str) -> None:
        return


def _options(tmp_path: Path) -> RuntimeOptions:
    return RuntimeOptions(
        delay_seconds=0.1,
        output_dir=tmp_path,
        headless=True,
        all_books=False,
        allow_partial=False,
        keep_images=False,
        ocr_enabled=False,
        ocr_by_book={},
        ocr_profile=OcrProfile("balanced", "Balanced", 2, 1.4),
        forget_login=False,
    )


def test_capture_page_when_ready_rejects_blank_first_page(monkeypatch, tmp_path: Path) -> None:
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.browser = SimpleNamespace(save_screenshot=lambda _path: None)
    session.options = _options(tmp_path)
    session._page_change_attempts = 2
    monkeypatch.setattr("digi2pdf.session.crop_image", lambda *_args: None)
    monkeypatch.setattr("digi2pdf.session.image_has_page_content", lambda _path: False)
    monkeypatch.setattr("digi2pdf.session.sleep", lambda _seconds: None)

    captured = session._capture_page_when_ready(
        tmp_path / "page.png",
        CropBox(left=0, top=0, right=1, bottom=1),
        previous_path=None,
    )

    assert not captured


def test_book_dir_for_duplicate_titles_allocates_suffix(tmp_path: Path) -> None:
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.options = _options(tmp_path)
    session._used_book_dirs = set()

    first = session._book_dir_for_title("book")
    session._used_book_dirs.add(first)
    second = session._book_dir_for_title("book")

    assert first == tmp_path / "book"
    assert second == tmp_path / "book-2"


def test_book_dir_for_existing_unmanaged_folder_allocates_suffix(tmp_path: Path) -> None:
    unmanaged = tmp_path / "book"
    unmanaged.mkdir()
    (unmanaged / "notes.txt").write_text("do not delete", encoding="utf-8")
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.options = _options(tmp_path)
    session._used_book_dirs = set()

    assert session._book_dir_for_title("book") == tmp_path / "book-2"
    assert (unmanaged / "notes.txt").exists()


def test_clean_managed_book_dir_only_removes_generated_files(tmp_path: Path) -> None:
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    (book_dir / ".digi2pdf-export").write_text("managed", encoding="utf-8")
    (book_dir / "0001.png").write_text("page", encoding="utf-8")
    (book_dir / "book.pdf").write_text("pdf", encoding="utf-8")
    (book_dir / "notes.txt").write_text("keep", encoding="utf-8")
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.options = _options(tmp_path)

    session._clean_managed_book_dir(book_dir)

    assert not (book_dir / "0001.png").exists()
    assert not (book_dir / "book.pdf").exists()
    assert (book_dir / "notes.txt").exists()


def test_select_sub_book_clicks_filtered_matching_element(monkeypatch, tmp_path: Path) -> None:
    clicked: list[str] = []

    class Element:
        def __init__(self, text: str) -> None:
            self.text = text

        def click(self) -> None:
            clicked.append(self.text)

    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.browser = SimpleNamespace(
        find_elements=lambda *_args: [Element(""), Element("First"), Element("Second")],
        switch_to=SimpleNamespace(window=lambda _handle: None),
        window_handles=[0, 1],
    )
    session.options = _options(tmp_path)
    session.sink = SimpleNamespace(step=lambda _message: None)
    monkeypatch.setattr(
        "digi2pdf.session.ask_sub_book",
        lambda _names: BookChoice(title="First", index=0),
    )
    monkeypatch.setattr("digi2pdf.session.sleep", lambda _seconds: None)

    assert session._select_sub_book("Parent") == "Parent/First"
    assert clicked == ["First"]


def test_save_books_raises_when_every_book_fails(monkeypatch, tmp_path: Path) -> None:
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.options = _options(tmp_path)
    session.sink = NullSink()
    session.browser = SimpleNamespace(window_handles=[0])
    session.current_book_index = None
    monkeypatch.setattr(session, "_open_book", lambda *_args: None)
    monkeypatch.setattr(
        session,
        "_save_current_book",
        lambda _title: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr("digi2pdf.session.sleep", lambda _seconds: None)
    monkeypatch.setattr("digi2pdf.session.ask_retry_failed_books", lambda _titles: False)

    with pytest.raises(RuntimeError, match="No books were exported successfully"):
        session._save_books([BookChoice("Book", 0)], [object()])


def test_save_books_reports_partial_failure_unless_allowed(monkeypatch, tmp_path: Path) -> None:
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    session.options = _options(tmp_path)
    session.sink = NullSink()
    session.browser = SimpleNamespace(window_handles=[0])
    session.current_book_index = None
    monkeypatch.setattr(session, "_open_book", lambda *_args: None)
    monkeypatch.setattr(
        session,
        "_save_current_book",
        lambda title: None
        if title == "First"
        else (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr("digi2pdf.session.sleep", lambda _seconds: None)
    monkeypatch.setattr("digi2pdf.session.ask_retry_failed_books", lambda _titles: False)

    with pytest.raises(RuntimeError, match="Some books failed"):
        session._save_books([BookChoice("First", 0), BookChoice("Second", 1)], [object(), object()])


def test_save_books_allows_partial_when_enabled(monkeypatch, tmp_path: Path) -> None:
    session = Digi2PDFSession.__new__(Digi2PDFSession)
    options = _options(tmp_path)
    session.options = RuntimeOptions(**{**options.__dict__, "allow_partial": True})
    session.sink = NullSink()
    session.browser = SimpleNamespace(window_handles=[0])
    session.current_book_index = None
    monkeypatch.setattr(session, "_open_book", lambda *_args: None)
    monkeypatch.setattr(
        session,
        "_save_current_book",
        lambda title: None
        if title == "First"
        else (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr("digi2pdf.session.sleep", lambda _seconds: None)
    monkeypatch.setattr("digi2pdf.session.ask_retry_failed_books", lambda _titles: False)

    assert session._save_books([BookChoice("First", 0), BookChoice("Second", 1)], [object(), object()])
