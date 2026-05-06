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
    "OCRmyPDF": ("ocrmypdf", "ocrmypdf"),
    "Pillow": ("PIL", "pillow"),
    "Platformdirs": ("platformdirs", "platformdirs"),
    "Questionary": ("questionary", "questionary"),
    "Rich": ("rich", "rich"),
    "Selenium": ("selenium", "selenium"),
}


OCR_CHECK_NAMES = {"Tesseract", "OCRmyPDF"}
OCR_SYSTEM_CHECK_NAMES = {"Tesseract"}


def run_python_dependency_checks() -> list[PreflightCheck]:
    if is_frozen_app():
        return []

    return [
        _python_package_check(label, module_name)
        for label, (module_name, _package_name) in PYTHON_DEPENDENCIES.items()
    ]


def run_bundled_runtime_checks() -> list[PreflightCheck]:
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

    if missing.intersection(OCR_SYSTEM_CHECK_NAMES):
        actions.extend(_ocr_install_actions(missing))

    return _dedupe_actions(actions)


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def install_missing_dependencies(checks: list[PreflightCheck]) -> bool:
    actions = install_actions_for(checks)
    for action in actions:
        result = subprocess.run(action.command, check=False)
        if result.returncode != 0:
            return False
    refresh_installed_dependency_paths()
    return True


def refresh_installed_dependency_paths() -> None:
    if platform.system() != "Windows":
        return

    paths = [os.environ.get("PATH", "")]
    try:
        import winreg

        for root, subkey in (
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        ):
            try:
                with winreg.OpenKey(root, subkey) as key:
                    value, _value_type = winreg.QueryValueEx(key, "Path")
            except OSError:
                continue
            paths.append(value)
    except Exception:
        pass

    for path in _windows_tool_parent_candidates():
        if path.exists():
            paths.append(str(path))

    seen: set[str] = set()
    merged: list[str] = []
    for path_list in paths:
        for path in path_list.split(os.pathsep):
            normalized = path.strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
    os.environ["PATH"] = os.pathsep.join(merged)


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
    if path is None:
        path = _candidate_binary_path(binary_name)
    return PreflightCheck(
        label,
        path is not None,
        str(path) if path else "missing",
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
        "Install Google Chrome from https://www.google.com/chrome/ before starting Digi2PDF.",
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


def _candidate_binary_path(binary_name: str) -> Path | None:
    if platform.system() != "Windows":
        return None

    executable_name = binary_name if binary_name.endswith(".exe") else f"{binary_name}.exe"
    for parent in _windows_tool_parent_candidates():
        candidate = parent / executable_name
        if candidate.exists():
            return candidate
    return None


def _windows_tool_parent_candidates() -> list[Path]:
    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root:
            continue
        base = Path(root)
        candidates.extend(
            [
                base / "Tesseract-OCR",
                base / "OCRmyPDF",
                base / "OCRmyPDF" / "bin",
                base / "Programs" / "OCRmyPDF",
                base / "Programs" / "OCRmyPDF" / "bin",
                base / "Python312" / "Scripts",
            ]
        )
    return candidates


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
                (
                    "winget",
                    "install",
                    "--id",
                    "Google.Chrome",
                    "-e",
                    "--source",
                    "winget",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ),
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
        if "Tesseract" in missing:
            actions.append(
                InstallAction(
                    "Install Tesseract",
                    (
                        "winget",
                        "install",
                        "--id",
                        "UB-Mannheim.TesseractOCR",
                        "-e",
                        "--source",
                        "winget",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                        "--disable-interactivity",
                    ),
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
