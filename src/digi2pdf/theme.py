from __future__ import annotations

import itertools
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
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
        self._live: Live | None = None
        self._dashboard_titles: list[str] = []
        self._dashboard_options: object | None = None
        self._dashboard_ocr: dict[str, bool] = {}
        self._book_status: dict[str, str] = {}
        self._capture_pages: dict[str, int] = {}
        self._ocr_progress: dict[str, tuple[int, int, float | None]] = {}
        self._started_at = time.monotonic()
        self._current_book: str | None = None
        self._logs: list[tuple[str, str, str | None]] = []

    def hero(self) -> None:
        title = Text("Digi2PDF - Coded and opensourced by jx-grxf", style=f"bold {THEME.accent}")
        subtitle = Text("Digi4School ebooks -> private offline PDFs", style=THEME.muted)
        self.console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style=THEME.accent))

    def animated_intro(self) -> None:
        title = "Digi2PDF - Coded and opensourced by jx-grxf"
        subtitle = "Digi4School ebooks -> private offline PDFs"

        def frame(title_text: str, subtitle_text: str = "") -> Panel:
            content = Text.assemble(
                Text(title_text, style=f"bold {THEME.accent}"),
                "\n",
                Text(subtitle_text, style=THEME.muted),
            )
            return Panel.fit(content, border_style=THEME.accent)

        with Live(frame(""), console=self.console, refresh_per_second=24, transient=True) as live:
            for index in range(1, len(title) + 1):
                live.update(frame(title[:index]))
                time.sleep(0.015)
            for index in range(1, len(subtitle) + 1):
                live.update(frame(title, subtitle[:index]))
                time.sleep(0.015)
        self.hero()

    def info_table(self) -> None:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style=THEME.muted)
        table.add_column(style=THEME.text)
        table.add_row("platforms", "macOS, Windows, Linux source install")
        table.add_row("engine", "Chrome automation, Pillow PDF export, optional OCR")
        table.add_row("controls", "Arrow keys, Space to select, Enter to continue")
        self.console.print(table)

    def tutorial(self) -> None:
        table = Table(show_header=True, header_style=f"bold {THEME.accent}", expand=True)
        table.add_column("Step", style=THEME.muted, no_wrap=True)
        table.add_column("What happens", style=THEME.text)
        table.add_row("Login", "Use your own Digi4School account. Password input is masked and can be saved only after a successful login.")
        table.add_row("Books", "Chrome opens the library, then you choose all books or selected books with Space and Enter.")
        table.add_row("OCR", "OCR is optional. It makes the PDF searchable, but needs Tesseract and takes longer.")
        table.add_row("Output", "Each book is exported into a managed folder in your chosen output directory.")
        table.add_row("Legal", "Export only books you may access and use privately. Do not redistribute generated PDFs.")
        self.console.print(Panel(table, title="First run guide", border_style=THEME.accent))

    def step(self, message: str) -> None:
        self._emit("●", message, THEME.accent)

    def warn(self, message: str) -> None:
        self._emit("▲", message, THEME.warning)

    def error(self, message: str) -> None:
        self._emit("✕", message, THEME.error)

    def success(self, message: str) -> None:
        self._emit("✓", message, THEME.success)

    def start_dashboard(self, titles: list[str], options: object, ocr_by_title: dict[str, bool]) -> None:
        self._dashboard_titles = titles
        self._dashboard_options = options
        self._dashboard_ocr = ocr_by_title
        self._book_status = dict.fromkeys(titles, "queued")
        self._started_at = time.monotonic()
        self._logs.clear()
        self._live = Live(
            self._render_dashboard(),
            console=self.console,
            refresh_per_second=8,
            transient=False,
            screen=False,
        )
        self._live.start()

    def finish_dashboard(self) -> None:
        if self._live is not None:
            self._refresh_dashboard()
            self._live.stop()
            self._live = None

    def start_book(self, title: str) -> None:
        self._current_book = title
        self._book_status[title] = "running"
        self._refresh_dashboard()

    def finish_book(self, title: str, pdf_path: Path) -> None:
        self._book_status[title] = "done"
        self._emit("✓", f"PDF written: {pdf_path}", THEME.success, title)
        self._refresh_dashboard()

    def capture_progress(self, title: str, page: int) -> None:
        self._capture_pages[title] = page
        self._emit("●", f"Captured page {page}", THEME.accent, title)
        self._refresh_dashboard()

    def ocr_progress(
        self, title: str, completed: int, total: int, eta_seconds: float | None
    ) -> None:
        self._ocr_progress[title] = (completed, total, eta_seconds)
        self._book_status[title] = "ocr"
        self._refresh_dashboard()

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

    def _emit(self, symbol: str, message: str, style: str, title: str | None = None) -> None:
        if self._live is None:
            self.console.print(f"[{style}]{symbol}[/] {message}")
            return
        self._logs.append((symbol, message, title))
        self._logs = self._logs[-80:]
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        if self._live is not None:
            self._live.update(self._render_dashboard())

    def _render_dashboard(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._render_summary(), name="summary", size=9),
            Layout(name="body"),
        )
        layout["body"].split_row(
            Layout(self._render_current_book(), name="current", size=34),
            Layout(self._render_logs(), name="logs"),
        )
        return layout

    def _render_summary(self) -> Panel:
        table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        table.add_column(style=THEME.muted, no_wrap=True)
        table.add_column(style=THEME.text)
        elapsed = time.monotonic() - self._started_at
        done = sum(1 for status in self._book_status.values() if status == "done")
        total = len(self._dashboard_titles)
        remaining_books = max(total - done, 0)
        eta = self._estimate_total_eta(remaining_books, elapsed)
        options = self._dashboard_options
        output_dir = getattr(options, "output_dir", "-")
        profile = getattr(getattr(options, "ocr_profile", None), "label", "-")
        total_status = (
            f"elapsed {_format_duration(elapsed)} • scanning pages"
            if eta is None
            else f"elapsed {_format_duration(elapsed)} • eta {_format_duration(eta)}"
        )
        titles = _truncate(f"{', '.join(self._dashboard_titles[:3])}{' ...' if total > 3 else ''}", 64)
        table.add_row("books", f"{done}/{total} done • {titles}")
        table.add_row("output", _truncate(str(output_dir), 76))
        table.add_row("ocr", f"{profile} • {self._ocr_count()} selected")
        table.add_row("total", total_status)
        return Panel(table, title="Export job", border_style=THEME.accent)

    def _render_current_book(self) -> Panel:
        title = self._current_book or "waiting"
        table = Table(show_header=False, box=None, expand=True)
        table.add_column(style=THEME.muted)
        table.add_column(style=THEME.text)
        if self._current_book:
            pages = self._capture_pages.get(self._current_book, 0)
            ocr = self._ocr_progress.get(self._current_book)
            table.add_row("book", _truncate(self._current_book, 40))
            table.add_row("status", self._book_status.get(self._current_book, "running"))
            table.add_row("pages", str(pages))
            if not ocr and self._book_status.get(self._current_book) == "running":
                table.add_row("phase", "finding final page")
            if ocr:
                completed, total, eta = ocr
                percent = int((completed / max(total, 1)) * 100)
                table.add_row("ocr", f"{_bar(percent)} {percent}%")
                table.add_row("ocr eta", _format_duration(eta))
        else:
            table.add_row("status", "waiting for book")
        return Panel(table, title=_truncate(title, 32), border_style=THEME.border)

    def _render_logs(self) -> Panel:
        text = Text()
        visible = self._logs[-24:]
        for symbol, message, title in visible:
            prefix = f"{title} " if title else ""
            style = _book_style(title) if title else THEME.text
            text.append(symbol, style=style)
            text.append(" ")
            if prefix:
                text.append(_truncate(prefix, 24), style=f"bold {style}")
            text.append(_truncate(message, 96), style=THEME.text)
            text.append("\n")
        if not visible:
            text.append("Waiting for live output...", style=THEME.muted)
        return Panel(text, title="live logs", border_style=THEME.accent)

    def _estimate_total_eta(self, remaining_books: int, elapsed: float) -> float | None:
        if remaining_books == 0:
            return 0
        done = sum(1 for status in self._book_status.values() if status == "done")
        if done == 0:
            return None
        return (elapsed / done) * remaining_books

    def _ocr_count(self) -> str:
        enabled = sum(1 for enabled in self._dashboard_ocr.values() if enabled)
        return f"{enabled}/{len(self._dashboard_ocr)}"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "calculating"
    seconds = max(0, int(seconds))
    minutes, rest = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {rest}s"
    return f"{rest}s"


def _bar(percent: int) -> str:
    filled = max(0, min(20, round(percent / 5)))
    return f"{('█' * filled).ljust(20, '░')}"


def _book_style(title: str | None) -> str:
    if not title:
        return THEME.text
    palette = [THEME.accent, THEME.success, THEME.warning, THEME.accent_soft, "#7DD3FC"]
    return palette[abs(hash(title)) % len(palette)]


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    if max_length <= 1:
        return value[:max_length]
    return f"{value[: max_length - 1]}…"
