from __future__ import annotations

import re
from pathlib import Path

SAFE_NAME_PATTERN = re.compile(r"[^\w .()\-]+", re.UNICODE)


def default_output_dir() -> Path:
    documents = Path.home() / "Documents"
    if documents.exists():
        return documents / "Digi2PDF"
    return Path.home() / "Digi2PDF"


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", name).strip(" ._")
    return cleaned or "book"
