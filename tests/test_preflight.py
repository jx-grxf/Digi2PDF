from __future__ import annotations

import subprocess

from digi2pdf.preflight import (
    InstallAction,
    PreflightCheck,
    install_actions_for,
    install_missing_dependencies,
    missing_required_checks,
    run_bundled_runtime_checks,
    run_python_dependency_checks,
)


def test_missing_required_checks_filters_failed_checks() -> None:
    checks = [
        PreflightCheck("Chrome", False, "missing"),
        PreflightCheck("Pillow", True, "installed"),
    ]

    missing = missing_required_checks(checks)

    assert missing == [checks[0]]


def test_install_actions_offer_chrome_on_macos_with_brew(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "digi2pdf.preflight.shutil.which",
        lambda binary: "/opt/homebrew/bin/brew" if binary == "brew" else None,
    )

    actions = install_actions_for([PreflightCheck("Chrome", False, "missing")])

    assert InstallAction(
        "Install Google Chrome with Homebrew",
        ("brew", "install", "--cask", "google-chrome"),
    ) in actions


def test_install_actions_offer_only_missing_ocr_native_tools(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "digi2pdf.preflight.shutil.which",
        lambda binary: "/opt/homebrew/bin/brew" if binary == "brew" else None,
    )

    actions = install_actions_for(
        [
            PreflightCheck("Tesseract", False, "missing"),
        ]
    )

    commands = [action.command for action in actions]
    assert ("brew", "install", "tesseract") in commands


def test_install_actions_do_not_install_present_ocr_tools(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "digi2pdf.preflight.shutil.which",
        lambda binary: "/opt/homebrew/bin/brew" if binary == "brew" else None,
    )

    actions = install_actions_for([PreflightCheck("Tesseract", False, "missing")])

    assert [action.command for action in actions] == [("brew", "install", "tesseract")]


def test_windows_winget_actions_pin_winget_source(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "digi2pdf.preflight.shutil.which",
        lambda binary: "C:/Windows/System32/winget.exe" if binary == "winget" else None,
    )

    actions = install_actions_for(
        [
            PreflightCheck("Chrome", False, "missing"),
            PreflightCheck("Tesseract", False, "missing"),
        ]
    )

    assert actions
    assert all("--source" in action.command for action in actions)
    assert all("winget" in action.command for action in actions)
    assert all("--accept-package-agreements" in action.command for action in actions)
    assert all("--accept-source-agreements" in action.command for action in actions)


def test_install_missing_dependencies_stops_after_failed_action(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    actions = [
        InstallAction("fail", ("false",)),
        InstallAction("skip", ("true",)),
    ]
    monkeypatch.setattr("digi2pdf.preflight.install_actions_for", lambda checks: actions)

    def fake_run(
        command: tuple[str, ...],
        *,
        check: bool,
    ) -> subprocess.CompletedProcess[tuple[str, ...]]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr("digi2pdf.preflight.subprocess.run", fake_run)

    assert not install_missing_dependencies([PreflightCheck("Chrome", False, "missing")])
    assert calls == [("false",)]


def test_frozen_binary_skips_python_dependency_checks(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.sys.frozen", True, raising=False)

    assert run_python_dependency_checks() == []


def test_frozen_binary_can_still_verify_bundled_runtime(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.sys.frozen", True, raising=False)

    checks = run_bundled_runtime_checks()

    assert {check.name for check in checks} >= {"Questionary", "Rich", "Selenium"}
