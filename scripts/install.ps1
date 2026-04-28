$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Error "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
}

uv tool install "git+https://github.com/jx-grxf/Digi2PDF.git" --force
Write-Host "Installed. Start with: digi2pdf"
