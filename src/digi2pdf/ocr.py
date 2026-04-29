from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from digi2pdf.models import OcrProfile, ProgressSink


class OcrUnavailableError(RuntimeError):
    pass


def recommended_ocr_jobs() -> int:
    cpu_count = os_cpu_count()
    if cpu_count >= 8:
        return 3
    if cpu_count >= 4:
        return 2
    return 1


def apply_ocr(
    pdf_path: Path,
    *,
    page_count: int,
    profile: OcrProfile,
    jobs: int,
    title: str,
    sink: ProgressSink,
) -> Path:
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
        str(profile.optimize_level),
        "--jobs",
        str(max(1, jobs)),
        str(pdf_path),
        str(ocr_path),
    ]
    started_at = time.monotonic()
    with tempfile.TemporaryFile("w+t") as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, text=True)
        while process.poll() is None:
            elapsed = time.monotonic() - started_at
            expected_total = max(page_count * profile.seconds_per_page / max(1, jobs), 1.0)
            completed_pages = min(page_count - 1, int((elapsed / expected_total) * page_count))
            eta = max(expected_total - elapsed, 0.0)
            sink.ocr_progress(title, completed_pages, page_count, eta)
            time.sleep(0.5)

        if process.returncode != 0:
            output.seek(0)
            details = output.read().strip() or "unknown OCR error"
            raise RuntimeError(f"OCR failed: {details}")

    sink.ocr_progress(title, page_count, page_count, 0)
    ocr_path.replace(pdf_path)
    return pdf_path


def os_cpu_count() -> int:
    try:
        import os

        return os.cpu_count() or 1
    except Exception:
        return 1
