#!/usr/bin/env bash
# ==============================================================================
# AudioGuard — Linux Build & Distribution Packager
# Builds standalone Linux x86_64 bundle and generates AudioGuard-Linux-x86_64.tar.gz
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "AudioGuard — Linux Standalone Build"
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
echo "[1/4] Cleaning previous build artifacts..."
rm -rf build dist dist-installer

# 2. Verify Audio Engine Crash Resilience
echo "[2/4] Running automated audio engine & crash resilience verification..."
"$PYTHON" verify_engine.py

# 3. Compile standalone Linux bundle via PyInstaller
echo "[3/4] Compiling AudioGuard via PyInstaller..."
"$PYINSTALLER" --noconfirm --onedir --windowed \
  --name "AudioGuard" \
  --collect-all "customtkinter" \
  --collect-all "sounddevice" \
  --collect-all "soundfile" \
  --collect-all "pystray" \
  --collect-all "PIL" \
  main.py

# 4. Package Distribution Tarball
echo "[4/4] Packaging distribution archive..."
mkdir -p dist-installer
PKG_NAME="${1:-AudioGuard-Linux-x86_64}"

tar -czf "dist-installer/${PKG_NAME}.tar.gz" -C dist AudioGuard

echo "================================================================="
echo "[SUCCESS] Linux Build Completed!"
echo "Package: dist-installer/${PKG_NAME}.tar.gz"
echo "================================================================="
