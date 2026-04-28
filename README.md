<div align="center">

# Digi2PDF

Professional cross-platform TUI for exporting owned Digi4School ebooks to clean PDFs.

![Python](https://img.shields.io/badge/python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/selenium-browser_automation-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-black?style=for-the-badge)

</div>

## Showcase

```text
╭──────────────────────────────╮
│ Digi2PDF                     │
│ owned Digi4School ebooks -> clean PDFs │
╰──────────────────────────────╯
● Opening Digi4School overview
● Capturing Mathematik 1
● Captured page 42
✓ Finished. Output folder: ~/Library/Application Support/Digi2PDF/exports
```

## Contents

- [Highlights](#highlights)
- [Why This Exists](#why-this-exists)
- [Current Workflow](#current-workflow)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Development](#development)
- [Roadmap](#roadmap)
- [License](#license)

## Highlights

| Feature | Description |
| --- | --- |
| Polished TUI | Rich and Questionary flow with strong contrast, status states, and arrow-key selections. |
| Cross-platform | Designed for macOS and Windows with Chrome + Selenium. |
| Secure login storage | Can store Digi4School credentials in the OS keychain or Windows Credential Manager. |
| Export location picker | Lets you choose the output folder interactively or via `--output-dir`. |
| Optional OCR | Can run an OCR post-process for searchable PDFs when `ocrmypdf` and Tesseract are available. |
| PDF pipeline | Captures pages, crops the book canvas, removes duplicate final page, and writes a PDF. |
| Provider handling | Supports Digi4School-style readers plus Scook and BiBox preparation paths. |
| Clean architecture | Browser automation, TUI, image handling, and runtime options are split into maintainable modules. |

## Why This Exists

Digi2PDF is a fresh, independent rewrite around the useful idea of converting personally accessible Digi4School books into PDFs for offline study. The goal is not a copied one-file script, but a maintainable private tool with a professional terminal interface.

Use it only for books you are allowed to access and export under your account, school rules, and local law.

## Current Workflow

1. Start the TUI.
2. Choose timing/output options.
3. Log in to Digi4School in the Selenium-controlled Chrome session.
4. Select one book or all visible books.
5. Digi2PDF detects the viewer type, captures pages, crops them, and writes a PDF.

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

- Python 3.12+
- Google Chrome
- `uv` for local development

## Quick Start

For normal use after the repository is public:

```sh
uv tool install git+https://github.com/jx-grxf/Digi2PDF.git
digi2pdf
```

Windows PowerShell:

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
uv run digi2pdf --forget-login
```

After global installation, drop `uv run`:

```sh
digi2pdf --show-browser
digi2pdf --output-dir ./exports
```

Credentials are saved only after a successful login and only if you confirm the prompt. On macOS they go into Keychain; on Windows they go into Credential Manager through `keyring`.

OCR is optional because it needs native tooling. Install the Python extra plus Tesseract/ocrmypdf support for your platform before using `--ocr`.

## Development

```sh
uv sync --dev
uv run ruff check .
uv run pytest
```

Build a local one-file binary for your current platform:

```sh
uv run pyinstaller --onefile --name digi2pdf --collect-all keyring --collect-all selenium packaging/digi2pdf_entry.py
```

Windows `.exe` builds are produced by the `Build Binaries` GitHub Actions workflow and uploaded as artifacts.

## Roadmap

- Add a true searchable book picker for very large libraries.
- Add resumable exports with per-book progress metadata.
- Add signed release builds for macOS and Windows.
- Add visual regression checks for crop-box detection.

## License

MIT
