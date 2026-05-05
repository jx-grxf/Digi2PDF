from __future__ import annotations

import pytest

from digi2pdf.cli import build_parser


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
