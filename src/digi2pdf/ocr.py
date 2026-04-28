from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class OcrUnavailableError(RuntimeError):
    pass


def apply_ocr(pdf_path: Path) -> Path:
    binary = shutil.which("ocrmypdf")
    if binary is None:
        raise OcrUnavailableError(
            "OCR is enabled, but 'ocrmypdf' is not installed. Install it with the ocr extra "
            "and make sure Tesseract is available."
        )

    ocr_path = pdf_path.with_name(f"{pdf_path.stem}.ocr.pdf")
    command = [
        binary,
        "--skip-text",
        "--optimize",
        "1",
        str(pdf_path),
        str(ocr_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "unknown OCR error"
        raise RuntimeError(f"OCR failed: {details}")

    ocr_path.replace(pdf_path)
    return pdf_path
