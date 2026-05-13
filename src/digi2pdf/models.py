from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class BookType(Enum):
    SUB_BOOKS = "sub_books"
    DIGI4SCHOOL = "digi4school"
    SCOOK = "scook"
    BIBOX = "bibox"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CropBox:
    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def from_browser_rect(cls, rect: dict[str, float], *, inset: int = 1) -> CropBox:
        return cls(
            left=int(rect["left"]) + inset,
            top=int(rect["top"]) + inset,
            right=int(rect["right"]),
            bottom=int(rect["bottom"]),
        )


@dataclass(frozen=True)
class BookChoice:
    title: str
    index: int


@dataclass(frozen=True)
class OcrProfile:
    name: str
    label: str
    optimize_level: int
    seconds_per_page: float


@dataclass(frozen=True)
class RuntimeOptions:
    delay_seconds: float
    output_dir: Path
    headless: bool
    all_books: bool
    allow_partial: bool
    keep_images: bool
    ocr_enabled: bool
    ocr_by_book: dict[int, bool]
    ocr_profile: OcrProfile
    forget_login: bool
    worker_setting: str | None = None
    interactive_ocr_recovery: bool = True


class ProgressSink(Protocol):
    def step(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def start_dashboard(
        self, titles: list[str], options: RuntimeOptions, ocr_by_title: dict[str, bool]
    ) -> None: ...

    def finish_dashboard(self) -> None: ...

    def start_book(self, title: str) -> None: ...

    def book_status(self, title: str, status: str) -> None: ...

    def fail_book(self, title: str, detail: str) -> None: ...

    def finish_book(self, title: str, pdf_path: Path) -> None: ...

    def capture_progress(self, title: str, page: int) -> None: ...

    def ocr_progress(
        self, title: str, completed: int, total: int, eta_seconds: float | None
    ) -> None: ...
