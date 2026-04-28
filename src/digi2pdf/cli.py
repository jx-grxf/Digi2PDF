from __future__ import annotations

import argparse
from pathlib import Path

from digi2pdf import __version__
from digi2pdf.browser import create_chrome_driver
from digi2pdf.models import RuntimeOptions
from digi2pdf.paths import default_output_dir
from digi2pdf.session import Digi2PDFSession
from digi2pdf.theme import Tui
from digi2pdf.tui import ask_confirm, ask_delay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digi2pdf",
        description="Export owned Digi4School ebooks to PDF with a polished terminal flow.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--show-browser", action="store_true", help="Run Chrome visibly for debugging.")
    parser.add_argument("--all", action="store_true", help="Try converting every visible book.")
    parser.add_argument("--keep-images", action="store_true", help="Keep intermediate PNG page captures.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tui = Tui()
    tui.hero()
    tui.info_table()

    delay = args.delay if args.delay is not None else ask_delay()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not ask_confirm(
        "Only export books you are allowed to use offline and in line with your school/account terms.",
        default=True,
    ):
        tui.warn("Cancelled before browser start.")
        return 1

    options = RuntimeOptions(
        delay_seconds=delay,
        output_dir=output_dir,
        headless=not args.show_browser,
        all_books=args.all,
        keep_images=args.keep_images,
    )

    try:
        with tui.busy("Starting Chrome"):
            browser = create_chrome_driver(headless=options.headless)
    except Exception as error:
        tui.error(f"Could not start Chrome/Selenium: {error}")
        return 1

    try:
        Digi2PDFSession(browser, options, tui).run()
    except KeyboardInterrupt:
        tui.warn("Interrupted by user.")
        return 130
    except Exception as error:
        tui.error(str(error))
        return 1
    finally:
        browser.quit()

    tui.success(f"Finished. Output folder: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
