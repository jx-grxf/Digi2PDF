from __future__ import annotations

from digi2pdf.theme import Tui


def test_hero_mentions_author() -> None:
    tui = Tui()
    with tui.console.capture() as capture:
        tui.hero()

    assert "Coded and opensourced by jx-grxf" in capture.get()
