from __future__ import annotations

import pytest

from digi2pdf.cli import (
    build_parser,
    ensure_python_dependencies,
    main,
    resolve_missing_dependencies,
    split_missing_checks,
)
from digi2pdf.preflight import PreflightCheck


class FakeTui:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warn(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)

    def busy(self, _message: str) -> FakeTui:
        return self

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


def test_delay_argument_rejects_negative_values() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--delay", "-2"])


def test_delay_argument_requires_minimum_value() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--delay", "0"])


def test_delay_argument_accepts_valid_float() -> None:
    parser = build_parser()

    args = parser.parse_args(["--delay", "0.25"])

    assert args.delay == 0.25


def test_allow_partial_flag_is_available() -> None:
    parser = build_parser()

    args = parser.parse_args(["--allow-partial"])

    assert args.allow_partial


def test_workers_argument_is_available() -> None:
    parser = build_parser()

    args = parser.parse_args(["--workers", "auto"])

    assert args.workers == "auto"


def test_frozen_binary_skips_python_package_installer(monkeypatch) -> None:
    monkeypatch.setattr("digi2pdf.preflight.sys.frozen", True, raising=False)
    monkeypatch.setattr(
        "digi2pdf.cli.run_python_dependency_checks",
        lambda: pytest.fail("frozen binaries must not probe pip packages"),
    )

    assert ensure_python_dependencies()


def test_frozen_binary_reports_incomplete_bundle_before_tui(monkeypatch, capsys) -> None:
    monkeypatch.setattr("digi2pdf.preflight.sys.frozen", True, raising=False)
    monkeypatch.setattr(
        "digi2pdf.cli.run_bundled_runtime_checks",
        lambda: [PreflightCheck("Questionary", False, "missing")],
    )

    assert main(["--version"]) == 1

    output = capsys.readouterr().out
    assert "EXE is incomplete" in output
    assert "Questionary" in output


def test_split_missing_checks_keeps_ocr_optional() -> None:
    checks = [
        PreflightCheck("Chrome", False, "missing"),
        PreflightCheck("Tesseract", False, "missing"),
        PreflightCheck("OCRmyPDF", False, "missing"),
    ]

    ocr_checks, blocking_checks = split_missing_checks(checks)

    assert [check.name for check in ocr_checks] == ["Tesseract", "OCRmyPDF"]
    assert [check.name for check in blocking_checks] == ["Chrome"]


def test_resolve_missing_dependencies_installs_ocr_when_requested(monkeypatch) -> None:
    checks = [
        PreflightCheck("Tesseract", False, "missing"),
        PreflightCheck("OCRmyPDF", False, "missing"),
    ]
    installed: list[list[PreflightCheck]] = []
    monkeypatch.setattr(
        "digi2pdf.cli.install_missing_dependencies",
        lambda missing: installed.append(missing) is None or True,
    )

    resolved, ocr_enabled = resolve_missing_dependencies(
        checks,
        require_ocr=True,
        tui=FakeTui(),
        ask_confirm=lambda _message, default=True: True,
    )

    assert resolved
    assert ocr_enabled
    assert installed == [checks]


def test_resolve_missing_dependencies_requires_explicit_no_ocr_choice(monkeypatch) -> None:
    checks = [PreflightCheck("Tesseract", False, "missing")]
    monkeypatch.setattr("digi2pdf.cli.install_actions_for", lambda _checks: [])

    resolved, ocr_enabled = resolve_missing_dependencies(
        checks,
        require_ocr=True,
        tui=FakeTui(),
        ask_confirm=lambda _message, default=True: True,
    )

    assert resolved
    assert not ocr_enabled
