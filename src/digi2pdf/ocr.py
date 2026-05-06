from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
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
    ocr_path = pdf_path.with_name(f"{pdf_path.stem}.ocr.pdf")
    command = _ocrmypdf_command()
    if command is not None:
        _apply_ocr_with_command(
            command,
            pdf_path,
            ocr_path,
            page_count=page_count,
            profile=profile,
            jobs=jobs,
            title=title,
            sink=sink,
        )
    else:
        _apply_ocr_with_api(
            pdf_path,
            ocr_path,
            page_count=page_count,
            profile=profile,
            jobs=jobs,
            title=title,
            sink=sink,
        )

    sink.ocr_progress(title, page_count, page_count, 0)
    ocr_path.replace(pdf_path)
    return pdf_path


def _ocrmypdf_command() -> list[str] | None:
    binary = shutil.which("ocrmypdf")
    if binary is not None:
        return [binary]
    return None


def _apply_ocr_with_command(
    command_prefix: list[str],
    pdf_path: Path,
    ocr_path: Path,
    *,
    page_count: int,
    profile: OcrProfile,
    jobs: int,
    title: str,
    sink: ProgressSink,
) -> None:
    command = [
        *command_prefix,
        "--skip-text",
        "--output-type",
        "pdf",
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


def _apply_ocr_with_api(
    pdf_path: Path,
    ocr_path: Path,
    *,
    page_count: int,
    profile: OcrProfile,
    jobs: int,
    title: str,
    sink: ProgressSink,
) -> None:
    try:
        import ocrmypdf
    except ImportError as error:
        raise OcrUnavailableError(
            "OCR is enabled, but OCRmyPDF is not bundled or installed."
        ) from error

    started_at = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            ocrmypdf.ocr,
            pdf_path,
            ocr_path,
            skip_text=True,
            output_type="pdf",
            optimize=profile.optimize_level,
            jobs=max(1, jobs),
            progress_bar=False,
        )
        while not future.done():
            elapsed = time.monotonic() - started_at
            expected_total = max(page_count * profile.seconds_per_page / max(1, jobs), 1.0)
            completed_pages = min(page_count - 1, int((elapsed / expected_total) * page_count))
            eta = max(expected_total - elapsed, 0.0)
            sink.ocr_progress(title, completed_pages, page_count, eta)
            time.sleep(0.5)
        result = future.result()

    if result not in (None, 0):
        raise RuntimeError(f"OCR failed with exit code {result}.")


def os_cpu_count() -> int:
    try:
        import os

        return os.cpu_count() or 1
    except Exception:
        return 1
