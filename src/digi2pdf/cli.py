from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from digi2pdf import __version__
from digi2pdf.preflight import (
    OCR_CHECK_NAMES,
    install_actions_for,
    install_missing_dependencies,
    missing_required_checks,
    resolve_chrome_binary,
    run_preflight_checks,
    run_python_dependency_checks,
)

OCR_PROFILE_NAMES = ("fast", "balanced", "best")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="digi2pdf",
        description="Export owned Digi4School ebooks to PDF with a polished terminal flow.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--delay", type=_delay_arg, default=None)
    parser.add_argument("--show-browser", action="store_true", help="Run Chrome visibly for debugging.")
    parser.add_argument("--all", action="store_true", help="Try converting every visible book.")
    parser.add_argument("--keep-images", action="store_true", help="Keep intermediate PNG page captures.")
    parser.add_argument("--ocr", action="store_true", help="Add a searchable OCR layer after export.")
    parser.add_argument("--no-ocr-prompt", action="store_true", help="Skip the interactive OCR question.")
    parser.add_argument(
        "--ocr-quality",
        choices=OCR_PROFILE_NAMES,
        default="balanced",
        help="OCR speed/quality profile.",
    )
    parser.add_argument("--forget-login", action="store_true", help="Delete saved Digi4School login first.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if not ensure_python_dependencies():
        return 1

    from digi2pdf.browser import create_chrome_driver
    from digi2pdf.credentials import clear_credentials
    from digi2pdf.models import RuntimeOptions
    from digi2pdf.paths import default_output_dir
    from digi2pdf.session import Digi2PDFSession
    from digi2pdf.theme import Tui
    from digi2pdf.tui import (
        OCR_PROFILES,
        ask_confirm,
        ask_delay,
        ask_ocr_enabled,
        ask_ocr_profile,
        ask_output_dir,
    )

    args = build_parser().parse_args(argv)
    tui = Tui()
    tui.animated_intro()
    tui.info_table()

    if args.forget_login:
        clear_credentials()
        tui.success("Saved Digi4School login cleared.")

    delay = args.delay if args.delay is not None else ask_delay()
    output_dir = (
        ask_output_dir(default_output_dir())
        if args.output_dir is None
        else args.output_dir.expanduser().resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_enabled = args.ocr or (not args.no_ocr_prompt and ask_ocr_enabled())
    ocr_profile = OCR_PROFILES[args.ocr_quality]
    if ocr_enabled and not args.no_ocr_prompt:
        ocr_profile = ask_ocr_profile(args.ocr_quality)

    if not ask_confirm(
        "Private-use notice: only export books you may legally access and use offline. Continue?",
        default=True,
    ):
        tui.warn("Cancelled before browser start.")
        return 1

    with tui.busy("Checking dependencies"):
        checks = run_preflight_checks(require_ocr=ocr_enabled)
    for check in checks:
        if check.ok:
            tui.success(f"{check.name}: {check.detail}")
        else:
            tui.warn(f"{check.name}: {check.detail}")
            if check.install_hint:
                tui.warn(f"{check.name} fix: {check.install_hint}")

    missing_checks = missing_required_checks(checks)
    if missing_checks:
        missing_ocr_only = all(check.name in OCR_CHECK_NAMES for check in missing_checks)
        actions = install_actions_for(missing_checks)
        if not actions:
            tui.error(
                "Required dependencies are missing and Digi2PDF cannot install them automatically."
            )
            if missing_ocr_only:
                tui.warn("Continuing without OCR.")
                ocr_enabled = False
            else:
                return 1
        elif missing_ocr_only:
            tui.warn("OCR dependencies can be installed now:")
            for action in actions:
                tui.warn(f"{action.label}: {shlex.join(action.command)}")
            if ask_confirm("Install OCR dependencies now?", default=True):
                with tui.busy("Installing OCR dependencies"):
                    installed = install_missing_dependencies(missing_checks)
                if not installed:
                    tui.warn("OCR dependency installation failed. Continuing without OCR.")
                    ocr_enabled = False
            else:
                tui.warn("Continuing without OCR.")
                ocr_enabled = False
        else:
            tui.warn("Missing dependencies can be installed now:")
            for action in actions:
                tui.warn(f"{action.label}: {shlex.join(action.command)}")

            if not ask_confirm("Install missing dependencies now?", default=True):
                tui.error("Cancelled because required dependencies are missing.")
                return 1

            with tui.busy("Installing missing dependencies"):
                installed = install_missing_dependencies(missing_checks)
            if not installed:
                tui.error("Dependency installation failed. Fix the commands above, then run Digi2PDF again.")
                return 1

        if not ocr_enabled and missing_ocr_only:
            checks = run_preflight_checks(require_ocr=False)
        else:
            with tui.busy("Rechecking dependencies"):
                checks = run_preflight_checks(require_ocr=ocr_enabled)
        still_missing = missing_required_checks(checks)
        if still_missing:
            for check in still_missing:
                tui.error(f"{check.name}: {check.detail}")
            return 1
        for check in checks:
            tui.success(f"{check.name}: {check.detail}")

    options = RuntimeOptions(
        delay_seconds=delay,
        output_dir=output_dir,
        headless=not args.show_browser,
        all_books=args.all,
        keep_images=args.keep_images,
        ocr_enabled=ocr_enabled,
        ocr_by_book={},
        ocr_profile=ocr_profile,
        forget_login=args.forget_login,
    )

    try:
        with tui.busy("Starting Chrome"):
            browser = create_chrome_driver(
                headless=options.headless,
                chrome_binary=resolve_chrome_binary(),
            )
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


def _delay_arg(value: str) -> float:
    try:
        delay = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("delay must be a number") from error
    if delay < 0.1:
        raise argparse.ArgumentTypeError("delay must be at least 0.1 seconds")
    return delay


def ensure_python_dependencies() -> bool:
    missing = missing_required_checks(run_python_dependency_checks())
    if not missing:
        return True

    print("Digi2PDF is missing required Python packages:")
    for check in missing:
        print(f"- {check.name}: {check.detail}")

    actions = install_actions_for(missing)
    if not actions:
        print("No automatic installer is available for these packages.")
        return False

    print("Install command:")
    for action in actions:
        print(f"- {shlex.join(action.command)}")

    try:
        answer = input("Install missing Python packages now? [Y/n] ").strip().lower()
    except EOFError:
        answer = "n"
    if answer not in {"", "y", "yes"}:
        return False

    if not install_missing_dependencies(missing):
        print("Python package installation failed.")
        return False
    return not missing_required_checks(run_python_dependency_checks())


if __name__ == "__main__":
    raise SystemExit(main())
