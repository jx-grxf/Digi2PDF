#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-manual}"
ICON_PATH="$ROOT_DIR/packaging/macos/AppIcon.icns"
APP_NAME="Digi2PDF"
APP_BUNDLE="$ROOT_DIR/dist/$APP_NAME.app"
RUNTIME_DIR="$APP_BUNDLE/Contents/Resources/digi2pdf"
DMG_STAGING_DIR="$ROOT_DIR/build/macos-dmg"
ARCH="$(uname -m)"

case "$ARCH" in
  arm64) RELEASE_ARCH="arm64" ;;
  x86_64) RELEASE_ARCH="x64" ;;
  *) RELEASE_ARCH="$ARCH" ;;
esac

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS app bundles can only be built on macOS." >&2
  exit 1
fi

if [[ ! -f "$ICON_PATH" ]]; then
  echo "Missing app icon: $ICON_PATH" >&2
  exit 1
fi

cd "$ROOT_DIR"
rm -rf "$APP_BUNDLE" "$DMG_STAGING_DIR" "$ROOT_DIR/build/macos-app"
uv run pyinstaller \
  --clean \
  --noconfirm \
  --onedir \
  --name digi2pdf \
  --collect-all keyring \
  --collect-all ocrmypdf \
  --collect-all PIL \
  --collect-all pypdfium2 \
  --collect-all platformdirs \
  --collect-all questionary \
  --collect-all rich \
  --collect-all selenium \
  packaging/digi2pdf_entry.py

mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"
cp -R "$ROOT_DIR/dist/digi2pdf" "$RUNTIME_DIR"
cp "$ICON_PATH" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"

cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>Digi2PDF</string>
  <key>CFBundleExecutable</key>
  <string>Digi2PDF</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>com.johannesgrof.digi2pdf</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Digi2PDF</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION#v}</string>
  <key>CFBundleVersion</key>
  <string>${VERSION#v}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
</dict>
</plist>
PLIST

cat > "$APP_BUNDLE/Contents/MacOS/Digi2PDF" <<'LAUNCHER'
#!/usr/bin/env zsh
set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$APP_ROOT/Resources/digi2pdf/digi2pdf"

# CLI calls such as `Digi2PDF.app/Contents/MacOS/Digi2PDF --version` must behave
# like a normal command. Finder launches without args open the interactive TUI in
# Terminal because Digi2PDF is intentionally terminal-based.
if [[ "$#" -gt 0 || -t 0 || "${DIGI2PDF_NO_TERMINAL_LAUNCH:-}" == "1" ]]; then
  exec "$CLI" "$@"
fi

osascript - "$CLI" <<'APPLESCRIPT'
on run argv
  set cliPath to item 1 of argv
  tell application "Terminal"
    activate
    do script quoted form of cliPath
  end tell
end run
APPLESCRIPT
LAUNCHER
chmod +x "$APP_BUNDLE/Contents/MacOS/Digi2PDF"

"$RUNTIME_DIR/digi2pdf" --version
plutil -lint "$APP_BUNDLE/Contents/Info.plist"
"$APP_BUNDLE/Contents/MacOS/Digi2PDF" --version

if command -v codesign >/dev/null 2>&1; then
  SIGN_IDENTITY="${MACOS_CODESIGN_IDENTITY:--}"
  if [[ "$SIGN_IDENTITY" == "-" ]]; then
    codesign --force --deep --sign "$SIGN_IDENTITY" "$APP_BUNDLE"
  else
    codesign --force --deep --options runtime --sign "$SIGN_IDENTITY" "$APP_BUNDLE"
  fi
  codesign --verify --deep --strict "$APP_BUNDLE"
fi

mkdir -p "$ROOT_DIR/release-assets"
ASSET_NAME="Digi2PDF-${VERSION}-macos-${RELEASE_ARCH}.dmg"
ASSET_PATH="$ROOT_DIR/release-assets/$ASSET_NAME"
rm -f "$ASSET_PATH" "$ASSET_PATH.sha256"

mkdir -p "$DMG_STAGING_DIR"
cp -R "$APP_BUNDLE" "$DMG_STAGING_DIR/"
ln -s /Applications "$DMG_STAGING_DIR/Applications"

if command -v create-dmg >/dev/null 2>&1; then
  if ! create-dmg \
    --volname "$APP_NAME $VERSION" \
    --window-pos 200 120 \
    --window-size 640 420 \
    --icon-size 96 \
    --icon "$APP_NAME.app" 160 180 \
    --app-drop-link 460 180 \
    "$ASSET_PATH" \
    "$DMG_STAGING_DIR"; then
    echo "create-dmg failed; falling back to hdiutil." >&2
    rm -f "$ASSET_PATH"
  fi
fi

if [[ ! -f "$ASSET_PATH" ]]; then
  hdiutil create \
    -volname "$APP_NAME $VERSION" \
    -srcfolder "$DMG_STAGING_DIR" \
    -ov \
    -format UDZO \
    "$ASSET_PATH"
fi

shasum -a 256 "$ASSET_PATH" \
  | sed "s|$ROOT_DIR/release-assets/||" \
  > "$ASSET_PATH.sha256"

hdiutil verify "$ASSET_PATH"

echo "$ASSET_PATH"
