#!/usr/bin/env bash
# Build a macOS .app and distributable .dmg on a Mac machine.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv-macos
source .venv-macos/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-macos.txt

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Gesture Synth" \
  --osx-bundle-identifier "com.gesturesynth.app" \
  --add-data "config.json:." \
  main.py

rm -f "dist/GestureSynth.dmg"
hdiutil create \
  -volname "Gesture Synth" \
  -srcfolder "dist/Gesture Synth.app" \
  -ov \
  -format UDZO \
  "dist/GestureSynth.dmg"

echo "Created dist/GestureSynth.dmg"
