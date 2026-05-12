# Changelog

## Unreleased

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
