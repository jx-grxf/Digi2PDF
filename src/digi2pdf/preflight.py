from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str
    install_hint: str | None = None


@dataclass(frozen=True)
class InstallAction:
    label: str
    command: tuple[str, ...]


PYTHON_DEPENDENCIES = {
    "Keyring": ("keyring", "keyring"),
    "Numpy": ("numpy", "numpy"),
    "Pillow": ("PIL", "pillow"),
    "Platformdirs": ("platformdirs", "platformdirs"),
    "Questionary": ("questionary", "questionary"),
    "Rich": ("rich", "rich"),
    "Selenium": ("selenium", "selenium"),
}


OCR_CHECK_NAMES = {"Tesseract", "OCRmyPDF"}


def run_python_dependency_checks() -> list[PreflightCheck]:
    return [
        _python_package_check(label, module_name)
        for label, (module_name, _package_name) in PYTHON_DEPENDENCIES.items()
    ]


def run_preflight_checks(*, require_ocr: bool) -> list[PreflightCheck]:
    checks = [
        PreflightCheck("Operating system", True, f"{platform.system()} {platform.release()}"),
        *run_python_dependency_checks(),
        _chrome_check(),
    ]
    if require_ocr:
        checks.append(_binary_check("Tesseract", "tesseract"))
        checks.append(_binary_check("OCRmyPDF", "ocrmypdf"))
    return checks


def missing_required_checks(checks: list[PreflightCheck]) -> list[PreflightCheck]:
    return [check for check in checks if not check.ok]


def install_actions_for(checks: list[PreflightCheck]) -> list[InstallAction]:
    missing = {check.name for check in missing_required_checks(checks)}
    actions: list[InstallAction] = []

    missing_python_packages = [
        package_name
        for label, (_module_name, package_name) in PYTHON_DEPENDENCIES.items()
        if label in missing
    ]
    if missing_python_packages:
        actions.append(
            InstallAction(
                "Install missing Python packages",
                (sys.executable, "-m", "pip", "install", *missing_python_packages),
            )
        )

    if "Chrome" in missing:
        actions.extend(_chrome_install_actions())

    if missing.intersection(OCR_CHECK_NAMES):
        actions.extend(_ocr_install_actions(missing))

    return _dedupe_actions(actions)


def install_missing_dependencies(checks: list[PreflightCheck]) -> bool:
    actions = install_actions_for(checks)
    for action in actions:
        result = subprocess.run(action.command, check=False)
        if result.returncode != 0:
            return False
    return True


def _python_package_check(label: str, module_name: str) -> PreflightCheck:
    ok = importlib.util.find_spec(module_name) is not None
    return PreflightCheck(
        label,
        ok,
        "installed" if ok else "missing",
        None if ok else f"Install the Python package that provides {module_name}.",
    )


def _binary_check(label: str, binary_name: str) -> PreflightCheck:
    path = shutil.which(binary_name)
    return PreflightCheck(
        label,
        path is not None,
        path or "missing",
        None if path else f"Install '{binary_name}' and make sure it is on PATH.",
    )


def _chrome_check() -> PreflightCheck:
    chrome_binary = resolve_chrome_binary()
    if chrome_binary is not None:
        return PreflightCheck("Chrome", True, str(chrome_binary))

    return PreflightCheck(
        "Chrome",
        False,
        "missing",
        "Install Google Chrome or Chromium before starting the browser.",
    )


def resolve_chrome_binary() -> Path | None:
    env_binary = os.environ.get("DIGI2PDF_CHROME_BINARY")
    if env_binary:
        path = Path(env_binary).expanduser()
        if path.exists():
            return path

    candidates = ["google-chrome", "chrome", "chromium", "chromium-browser"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return Path(path)

    for path in _platform_chrome_candidates():
        if path.exists():
            return path

    return None


def _platform_chrome_candidates() -> list[Path]:
    system = platform.system()
    if system == "Darwin":
        return [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    if system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        return [
            Path(root) / "Google/Chrome/Application/chrome.exe"
            for root in roots
            if root
        ]
    return []


def _chrome_install_actions() -> list[InstallAction]:
    system = platform.system()
    if system == "Darwin" and shutil.which("brew"):
        return [
            InstallAction(
                "Install Google Chrome with Homebrew",
                ("brew", "install", "--cask", "google-chrome"),
            )
        ]
    if system == "Windows" and shutil.which("winget"):
        return [
            InstallAction(
                "Install Google Chrome with winget",
                ("winget", "install", "--id", "Google.Chrome", "-e"),
            )
        ]
    return []


def _ocr_install_actions(missing: set[str]) -> list[InstallAction]:
    actions: list[InstallAction] = []
    system = platform.system()
    if system == "Darwin" and shutil.which("brew"):
        packages = []
        if "OCRmyPDF" in missing:
            packages.append("ocrmypdf")
        if "Tesseract" in missing:
            packages.append("tesseract")
        if packages:
            actions.append(InstallAction("Install OCR native tools", ("brew", "install", *packages)))
    elif system == "Windows" and shutil.which("winget"):
        if "OCRmyPDF" in missing:
            actions.append(
                InstallAction(
                    "Install OCRmyPDF",
                    ("winget", "install", "--id", "OCRmyPDF.OCRmyPDF", "-e"),
                )
            )
        if "Tesseract" in missing:
            actions.append(
                InstallAction(
                    "Install Tesseract",
                    ("winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e"),
                )
            )
    elif system == "Linux":
        packages = []
        if "OCRmyPDF" in missing:
            packages.append("ocrmypdf")
        if "Tesseract" in missing:
            packages.append("tesseract-ocr")
        if packages and shutil.which("apt-get"):
            actions.append(
                InstallAction(
                    "Install OCR native tools with apt",
                    ("sudo", "apt-get", "install", "-y", *packages),
                )
            )
    elif "OCRmyPDF" in missing:
        actions.append(
            InstallAction(
                "Install OCRmyPDF Python package",
                (sys.executable, "-m", "pip", "install", "ocrmypdf"),
            )
        )
    return actions


def _dedupe_actions(actions: list[InstallAction]) -> list[InstallAction]:
    deduped: list[InstallAction] = []
    seen: set[tuple[str, ...]] = set()
    for action in actions:
        if action.command in seen:
            continue
        seen.add(action.command)
        deduped.append(action)
    return deduped
