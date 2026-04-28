#!/usr/bin/env sh
set -eu

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

uv tool install "git+https://github.com/jx-grxf/Digi2PDF.git" --force
echo "Installed. Start with: digi2pdf"
