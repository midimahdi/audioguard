#!/usr/bin/env bash
# ==============================================================================
# AudioGuard — macOS Build & DMG Packager
# Builds AudioGuard.app bundle and generates AudioGuard-macOS.dmg
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "AudioGuard — macOS Standalone Build"
echo "================================================================="

# Detect virtual environment Python or fallback
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
  PYINSTALLER="$SCRIPT_DIR/.venv/bin/pyinstaller"
else
  PYTHON="python3"
  PYINSTALLER="pyinstaller"
fi

# 1. Clean previous build artifacts
echo "[1/6] Cleaning previous build artifacts..."
rm -rf build dist dist-dmg dist-installer

# 2. Verify Audio Engine Crash Resilience
echo "[2/6] Running automated audio engine & crash resilience verification..."
"$PYTHON" verify_engine.py

# 3. Compile standalone macOS .app bundle via PyInstaller
echo "[3/6] Compiling AudioGuard.app via PyInstaller..."
"$PYINSTALLER" --noconfirm --onedir --windowed \
  --name "AudioGuard" \
  --collect-all "customtkinter" \
  --collect-all "sounddevice" \
  --collect-all "soundfile" \
  --collect-all "PIL" \
  main.py

# 4. Inject macOS Security & App Nap Permissions into Info.plist
echo "[4/6] Configuring Info.plist for CoreAudio & App Nap permissions..."
PLIST_FILE="dist/AudioGuard.app/Contents/Info.plist"

/usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string 'AudioGuard requires microphone access to record lossless backup audio feeds.'" "$PLIST_FILE" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSMicrophoneUsageDescription 'AudioGuard requires microphone access to record lossless backup audio feeds.'" "$PLIST_FILE"

/usr/libexec/PlistBuddy -c "Add :NSAppSleepDisabled bool true" "$PLIST_FILE" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :NSAppSleepDisabled true" "$PLIST_FILE"

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString '1.5.2'" "$PLIST_FILE" 2>/dev/null || true

# 5. Ad-hoc Code Signing
echo "[5/6] Applying ad-hoc codesign to bundle..."
codesign --force --deep --sign - "dist/AudioGuard.app"

# 6. Package Drag-and-Drop DMG & ZIP Archives
echo "[6/6] Generating distribution DMG and ZIP..."
PKG_NAME="${1:-AudioGuard-macOS}"
mkdir -p dist-installer
mkdir -p dist-dmg
cp -R "dist/AudioGuard.app" dist-dmg/
ln -s /Applications dist-dmg/Applications
hdiutil create -volname "AudioGuard" -srcfolder dist-dmg -ov -format UDZO "dist-installer/${PKG_NAME}.dmg"
rm -rf dist-dmg

# Also create zip bundle
ditto -c -k --sequesterRsrc --keepParent "dist/AudioGuard.app" "dist-installer/${PKG_NAME}.zip"

echo "================================================================="
echo "[SUCCESS] macOS Build Completed!"
echo "DMG: dist-installer/${PKG_NAME}.dmg"
echo "ZIP: dist-installer/${PKG_NAME}.zip"
echo "================================================================="
