<div align="center">

# Digi2PDF

Are you also sick of using this stupid Digi4... web editor and finally want to have a clean and searchable PDF of the books you paid for? 

![Python](https://img.shields.io/badge/python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/selenium-browser_automation-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/jx-grxf/Digi2PDF/ci.yml?branch=main&style=for-the-badge&label=ci)
![License](https://img.shields.io/badge/license-MIT-black?style=for-the-badge)

</div>

## Showcase

```text
╭────────────────────────────────────────╮
│ Digi2PDF                               │
│ owned Digi4School ebooks -> clean PDFs │
╰────────────────────────────────────────╯
platform macOS + Windows
engine Python, Selenium, Pillow
Terminal ui

✓ Chrome: /Applications/Google Chrome.app
✓ Tesseract: /opt/homebrew/bin/tesseract
● Live dashboard: selected books, capture phase, OCR progress, and scrollable logs
✓ Finished. Output folder: ~/Documents/Digi2PDF
```

## Contents

- [Digi2PDF](#digi2pdf)
  - [Showcase](#showcase)
  - [Contents](#contents)
  - [Highlights](#highlights)
  - [Why This Exists](#why-this-exists)
  - [Current Workflow](#current-workflow)
  - [Tech Stack](#tech-stack)
  - [Requirements](#requirements)
  - [Quick Start](#quick-start)
  - [Usage](#usage)
  - [Legal Notice](#legal-notice)
  - [Development](#development)
  - [Roadmap](#roadmap)
  - [License](#license)

## Highlights

| Feature | Description |
| --- | --- |
| Polished TUI | Fast terminal UI flow with strong contrast, status states, and arrow-key selections. |
| Multi-book picker | Select one or many books with Space and start the batch with Enter. |
| Live dashboard | Shows selected books, output path, capture phase, OCR decisions, per-book OCR progress, and scrollable colored logs. |
| Cross-platform | Designed for macOS and Windows with Chrome + Selenium. |
| Secure login storage | Can store Digi4.... credentials in the OS keychain or Windows Credential Manager. |
| Export location picker | Defaults to `~/Documents/Digi2PDF` on macOS and still lets you override the folder. |
| Optional OCR | Can run a searchable OCR post-process with fast, balanced, and best profiles when OCRmyPDF and Tesseract are available. |
| PDF pipeline | Captures stable pages, crops the book canvas, waits for page changes, removes the duplicate final page, and writes a PDF. |
| Provider handling | Supports Digi4....-style readers plus Scook and BiBox preparation paths. |
| Clean architecture | Browser automation, TUI, image handling, and runtime options are split into maintainable modules. |

## Why This Exists

Digi2PDF is a fresh, independent rewrite around the useful idea of converting personally accessible Digi4School books into PDFs for offline study. The goal is not a copied one-file script, but a maintainable private tool with a professional terminal interface.

Use it only for books you are allowed to access and export under your account, school rules, and local law. Digi2PDF is intended for private offline study workflows, not for redistribution or bypassing access restrictions.

## Current Workflow

1. Start the TUI.
2. Confirm the private-use notice.
3. Choose timing/output/OCR options.
4. Digi2PDF checks the operating system, Python dependencies, Chrome, and OCR tooling when OCR is enabled.
5. Log in to Digi4School in the Selenium-controlled Chrome session.
6. Select one or many books with Space and Enter.
7. Choose which selected books should receive OCR.
8. Digi2PDF detects the viewer type, captures stable page images, waits for page changes, writes a PDF, optionally adds OCR, and removes intermediate page images unless `--keep-images` is set.

## Tech Stack

| Area | Tooling |
| --- | --- |
| Language | Python 3.12+ |
| Browser automation | Selenium + Chrome |
| TUI | Rich + Questionary |
| Image/PDF | Pillow + NumPy |
| Packaging | uv + hatchling |
| Quality | Ruff + Pytest + GitHub Actions |

## Requirements

- Google Chrome
- Python 3.12+ when installing as a Python CLI
- `uv` for the recommended CLI installation and local development
- No Python or `uv` installation is needed when using the Windows release EXE
- Optional OCR: Tesseract. The Windows release EXE bundles the OCRmyPDF Python runtime; normal Python installs receive it as a package dependency.

## Quick Start

Recommended CLI install:

```sh
uv tool install git+https://github.com/jx-grxf/Digi2PDF.git
digi2pdf
```

Windows users can either use the same CLI install or download the latest `digi2pdf-*-windows-x64.exe` release asset:

```powershell
.\digi2pdf-v0.0.0-windows-x64.exe
```

The EXE bundles the required Python packages. Google Chrome still needs to be installed separately because Selenium controls the real browser.

If you prefer the Python CLI:

```powershell
uv tool install git+https://github.com/jx-grxf/Digi2PDF.git
digi2pdf
```

Local development:

```sh
uv sync --dev
uv run digi2pdf
```

## Usage

```sh
uv run digi2pdf --output-dir ./exports
uv run digi2pdf --show-browser --delay 1.0
uv run digi2pdf --all --keep-images
uv run digi2pdf --ocr
uv run digi2pdf --ocr --ocr-quality fast
uv run digi2pdf --forget-login
```

After global installation, drop `uv run`:

```sh
digi2pdf --show-browser
digi2pdf --output-dir ./exports
```

Credentials are saved only after a successful login and only if you confirm the prompt. On macOS they go into Keychain; on Windows they go into Credential Manager through `keyring`.

OCR is optional because it still needs native Tesseract tooling. When OCR is enabled and a system dependency is missing, Digi2PDF offers install commands, rechecks the result, and asks for a restart if the new tools are not visible in the current terminal yet. The CLI estimates OCR ETA from the selected quality profile, page count, and local CPU job count. During page capture, Digi2PDF shows the active scan phase instead of a fake ETA because the final page count is only known after the reader stops advancing.

## Legal Notice

Digi2PDF is for private use with ebooks you are already allowed to access. Do not use it to share, sell, upload, or redistribute copyrighted material, and do not use it in ways that violate your school, account, platform, or local legal requirements.

## Development

```sh
uv sync --dev
uv run ruff check .
uv run pytest
```

Build a local one-file binary for your current platform:

```sh
uv run pyinstaller --clean --noconfirm --onefile --name digi2pdf --collect-all keyring --collect-all PIL --collect-all platformdirs --collect-all questionary --collect-all rich --collect-all selenium packaging/digi2pdf_entry.py
```

Windows `.exe` builds are produced by the `Build Binaries` GitHub Actions workflow when a GitHub release is published. The workflow runs tests, smoke-tests `digi2pdf.exe --version`, and uploads the versioned EXE plus a SHA256 checksum to the release assets.

## Roadmap

- Add a true searchable book picker for very large libraries.
- Add resumable exports with per-book progress metadata.
- Add signed release builds for macOS and Windows.
- Add visual regression checks for crop-box detection.
- Add safe parallel browser workers after the Selenium session model is isolated per book.

## License

MIT
