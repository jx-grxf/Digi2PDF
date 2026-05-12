from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_does_not_use_placeholder_windows_exe_version() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "digi2pdf-v0.0.0-windows-x64.exe" not in readme


def test_readme_pyinstaller_command_matches_release_runtime_collections() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    for package in ("keyring", "ocrmypdf", "PIL", "pypdfium2", "platformdirs", "questionary", "rich", "selenium"):
        flag = f"--collect-all {package}"
        assert flag in readme
        assert flag in workflow
