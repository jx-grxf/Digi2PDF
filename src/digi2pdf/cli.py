from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from digi2pdf import __version__
from digi2pdf.preflight import (
    OCR_CHECK_NAMES,
    PreflightCheck,
    install_actions_for,
    install_missing_dependencies,
    is_frozen_app,
    missing_required_checks,
    refresh_installed_dependency_paths,
    resolve_chrome_binary,
    run_bundled_runtime_checks,
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
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Exit successfully when at least one selected book was exported.",
    )
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
    if is_frozen_app():
        missing_bundle_checks = missing_required_checks(run_bundled_runtime_checks())
        if missing_bundle_checks:
            print("This Digi2PDF EXE is incomplete and cannot start the TUI.")
            print("Download the Windows release asset again or rebuild the EXE from CI.")
            print("Missing bundled modules:")
            for check in missing_bundle_checks:
                print(f"- {check.name}: {check.detail}")
            return 1
    elif not ensure_python_dependencies():
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
        ask_first_run,
        ask_ocr_enabled,
        ask_ocr_profile,
        ask_output_dir,
        ask_runtime_recovery,
    )

    args = build_parser().parse_args(argv)
    tui = Tui()
    tui.animated_intro()
    tui.info_table()

    if ask_first_run():
        tui.tutorial()

    if args.forget_login:
        clear_credentials()
        tui.success("Saved Digi4School login cleared.")

    if not ask_confirm(
        "Private-use notice: only export books you may legally access and use offline. Continue?",
        default=True,
    ):
        tui.warn("Cancelled before browser start.")
        return 1

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

    while True:
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
        if not missing_checks:
            break

        resolved, ocr_enabled = resolve_missing_dependencies(
            missing_checks,
            require_ocr=ocr_enabled,
            tui=tui,
            ask_confirm=ask_confirm,
        )
        if not resolved:
            if ask_runtime_recovery("Dependency setup did not finish. What now?") == "retry":
                continue
            return 1

        with tui.busy("Rechecking dependencies"):
            refresh_installed_dependency_paths()
            checks = run_preflight_checks(require_ocr=ocr_enabled)
        still_missing = missing_required_checks(checks)
        if still_missing:
            for check in still_missing:
                tui.error(f"{check.name}: {check.detail}")
            if ask_confirm("Restart Digi2PDF now to finish dependency setup?", default=True):
                restart_current_process()
                return 0
            if ask_runtime_recovery("Dependencies are still missing. What now?") == "retry":
                continue
            return 1
        for check in checks:
            tui.success(f"{check.name}: {check.detail}")
        break

    options = RuntimeOptions(
        delay_seconds=delay,
        output_dir=output_dir,
        headless=not args.show_browser,
        all_books=args.all,
        allow_partial=args.allow_partial,
        keep_images=args.keep_images,
        ocr_enabled=ocr_enabled,
        ocr_by_book={},
        ocr_profile=ocr_profile,
        forget_login=args.forget_login,
    )

    browser = None
    while browser is None:
        try:
            with tui.busy("Starting Chrome"):
                browser = create_chrome_driver(
                    headless=options.headless,
                    chrome_binary=resolve_chrome_binary(),
                )
        except Exception as error:
            tui.error(f"Could not start Chrome/Selenium: {error}")
            tui.warn("Install or update Google Chrome, then retry. Set DIGI2PDF_CHROME_BINARY for a custom Chrome path.")
            if ask_runtime_recovery("Chrome could not start. What now?") != "retry":
                return 1

    try:
        completed = Digi2PDFSession(browser, options, tui).run()
    except KeyboardInterrupt:
        tui.warn("Interrupted by user.")
        return 130
    except Exception as error:
        tui.error(str(error))
        return 1
    finally:
        browser.quit()

    tui.success(f"Finished. Output folder: {output_dir}")
    return 0 if completed else 1


def _delay_arg(value: str) -> float:
    try:
        delay = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("delay must be a number") from error
    if delay < 0.1:
        raise argparse.ArgumentTypeError("delay must be at least 0.1 seconds")
    return delay


def split_missing_checks(
    checks: list[PreflightCheck],
) -> tuple[list[PreflightCheck], list[PreflightCheck]]:
    missing_ocr_checks = [check for check in checks if check.name in OCR_CHECK_NAMES]
    blocking_checks = [check for check in checks if check.name not in OCR_CHECK_NAMES]
    return missing_ocr_checks, blocking_checks


def resolve_missing_dependencies(
    checks: list[PreflightCheck],
    *,
    require_ocr: bool,
    tui: object,
    ask_confirm: object,
) -> tuple[bool, bool]:
    missing_ocr_checks, blocking_checks = split_missing_checks(checks)
    actions = install_actions_for(checks)

    if actions:
        tui.warn("Missing dependencies can be installed now:")
        for action in actions:
            tui.warn(f"{action.label}: {shlex.join(action.command)}")

        if ask_confirm("Install missing dependencies now?", default=True):
            with tui.busy("Installing missing dependencies"):
                installed = install_missing_dependencies(checks)
            if installed:
                return True, require_ocr
            tui.error("Dependency installation failed.")
        else:
            tui.warn("Dependency installation skipped.")

    elif blocking_checks:
        tui.error("Required dependencies are missing and Digi2PDF cannot install them automatically.")

    if blocking_checks:
        for check in blocking_checks:
            tui.error(f"{check.name}: {check.detail}")
            if check.install_hint:
                tui.warn(f"{check.name} fix: {check.install_hint}")
        return False, require_ocr

    if missing_ocr_checks and ask_confirm("Continue without OCR for this run?", default=False):
        tui.warn("Continuing without OCR by user choice.")
        return True, False

    return False, require_ocr


def restart_current_process() -> None:
    os.execv(sys.executable, [sys.executable, *sys.argv])


def ensure_python_dependencies() -> bool:
    if is_frozen_app():
        return True

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
