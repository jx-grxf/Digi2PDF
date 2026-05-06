from __future__ import annotations

import pytest

from digi2pdf.cli import build_parser, ensure_python_dependencies, main
from digi2pdf.preflight import PreflightCheck


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
