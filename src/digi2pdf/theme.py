from __future__ import annotations

import itertools
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True)
class DigiTheme:
    accent: str = "#FF5A2D"
    accent_soft: str = "#FF9A6A"
    text: str = "#E8E3D5"
    muted: str = "#8B7F77"
    success: str = "#2FBF71"
    warning: str = "#FFB020"
    error: str = "#E23D2D"
    border: str = "#3C414B"


THEME = DigiTheme()
WAITING_PHRASES = (
    "rendering pages",
    "polishing margins",
    "nudging pixels",
    "building the PDF",
    "checking the book spine",
)
SPINNER_FRAMES = ("●○○", "○●○", "○○●", "○●○")


class Tui:
    def __init__(self) -> None:
        self.console = Console()

    def hero(self) -> None:
        title = Text("Digi2PDF", style=f"bold {THEME.accent}")
        subtitle = Text("owned Digi4School ebooks -> clean PDFs", style=THEME.muted)
        self.console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style=THEME.accent))

    def info_table(self) -> None:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style=THEME.muted)
        table.add_column(style=THEME.text)
        table.add_row("platform", "macOS + Windows")
        table.add_row("engine", "Python, Selenium, Pillow")
        table.add_row("ui", "Rich/Questionary terminal flow")
        self.console.print(table)

    def step(self, message: str) -> None:
        self.console.print(f"[{THEME.accent}]●[/] {message}")

    def warn(self, message: str) -> None:
        self.console.print(f"[{THEME.warning}]▲[/] {message}")

    def error(self, message: str) -> None:
        self.console.print(f"[{THEME.error}]✕[/] {message}")

    def success(self, message: str) -> None:
        self.console.print(f"[{THEME.success}]✓[/] {message}")

    @contextmanager
    def busy(self, message: str) -> Iterator[None]:
        progress = Progress(
            SpinnerColumn("dots", style=THEME.accent),
            TextColumn(f"[bold {THEME.accent}]{message}[/]"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        with progress:
            progress.add_task(message, total=None)
            yield

    def animated_status(self, activity: str) -> Live:
        started = time.monotonic()
        ticks = itertools.count()

        def render() -> Text:
            tick = next(ticks)
            frame = SPINNER_FRAMES[tick % len(SPINNER_FRAMES)]
            phrase = WAITING_PHRASES[(tick // 8) % len(WAITING_PHRASES)]
            elapsed = int(time.monotonic() - started)
            return Text.assemble(
                (frame, THEME.accent),
                " ",
                (activity, f"bold {THEME.text}"),
                " • ",
                (phrase, THEME.muted),
                " • ",
                (f"{elapsed}s", THEME.muted),
            )

        return Live(render(), console=self.console, refresh_per_second=8, transient=True)
