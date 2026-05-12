from __future__ import annotations

import re
from pathlib import Path

SAFE_NAME_PATTERN = re.compile(r"[^\w .()\-]+", re.UNICODE)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
MAX_FILENAME_LENGTH = 120


def default_output_dir() -> Path:
    documents = Path.home() / "Documents"
    if documents.exists():
        return documents / "Digi2PDF"
    return Path.home() / "Digi2PDF"


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", name).strip(" ._")
    if not cleaned:
        return "book"

    stem = cleaned.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}-book"

    if len(cleaned) > MAX_FILENAME_LENGTH:
        cleaned = cleaned[:MAX_FILENAME_LENGTH].rstrip(" ._")

    return cleaned or "book"
