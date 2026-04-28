from __future__ import annotations

import re
from pathlib import Path

from platformdirs import user_data_dir

SAFE_NAME_PATTERN = re.compile(r"[^\w .()\-]+", re.UNICODE)


def default_output_dir() -> Path:
    return Path(user_data_dir("Digi2PDF", "JohannesGrof")) / "exports"


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("_", name).strip(" ._")
    return cleaned or "book"
