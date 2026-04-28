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
class RuntimeOptions:
    delay_seconds: float
    output_dir: Path
    headless: bool
    all_books: bool
    keep_images: bool


class ProgressSink(Protocol):
    def step(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...
