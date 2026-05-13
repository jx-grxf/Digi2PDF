# Changelog

## 0.3.1

Released 2026-05-13.

### Highlights

- Multi-book exports can now run one book at a time, in recommended automatic parallel mode, or with an advanced manual session count.
- macOS releases now ship as a drag-to-Applications `Digi2PDF.app` DMG built by GitHub Actions.

### Fixed

- Parallel workers no longer open interactive OCR recovery prompts from background threads.
- Parallel exports fall back to serial mode when no saved Digi4School login is available.
- The macOS launcher now supports direct CLI smoke tests such as `Digi2PDF --version`.

### Improved

- The dashboard shows per-book starting and capturing states while multiple books are active.
- Manual session count defaults to the recommended worker count instead of the maximum.
- Release workflows now wait for both macOS and Windows assets before triggering the website rebuild.

## 0.3.0

Released 2026-05-12.

### Added

- First-run tutorial for login, book selection, OCR, output folders, Chrome, and legal/private-use limits.
- Recoverable login, Chrome startup, OCR, dependency, and per-book failure flows.
- `--allow-partial` for intentional partial-success batch exports.
- Windows-safe filename handling and managed export folder markers.
- OCR runtime diagnostics and Linux Chrome/Chromium install guidance.
- Security policy and public project metadata.

### Changed

- Password input now uses the themed prompt with `*` masking.
- Book selection now separates all-books export from manual selection.
- README wording, platform claims, and PyInstaller command now match the implementation more closely.

## 0.2.3

- Hardened Windows EXE runtime preflight and OCR dependency handling.
- Kept Chrome and Tesseract as external system dependencies for the Windows EXE.
