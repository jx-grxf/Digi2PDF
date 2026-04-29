from __future__ import annotations

import importlib.util
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def run_preflight_checks(*, require_ocr: bool) -> list[PreflightCheck]:
    checks = [
        PreflightCheck("Operating system", True, f"{platform.system()} {platform.release()}"),
        _python_package_check("Selenium", "selenium"),
        _python_package_check("Pillow", "PIL"),
        _python_package_check("Rich", "rich"),
        _chrome_check(),
    ]
    if require_ocr:
        checks.append(_binary_check("Tesseract", "tesseract"))
        checks.append(_binary_check("OCRmyPDF", "ocrmypdf"))
    return checks


def _python_package_check(label: str, module_name: str) -> PreflightCheck:
    ok = importlib.util.find_spec(module_name) is not None
    return PreflightCheck(label, ok, "installed" if ok else "missing")


def _binary_check(label: str, binary_name: str) -> PreflightCheck:
    path = shutil.which(binary_name)
    return PreflightCheck(label, path is not None, path or "missing")


def _chrome_check() -> PreflightCheck:
    candidates = ["google-chrome", "chrome", "chromium", "chromium-browser"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return PreflightCheck("Chrome", True, path)

    mac_path = Path("/Applications/Google Chrome.app")
    if mac_path.exists():
        return PreflightCheck("Chrome", True, str(mac_path))

    return PreflightCheck("Chrome", False, "missing")
