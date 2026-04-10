#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${1:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$ROOT/dist"
BUILD_ROOT="$ROOT/build"
SPEC_DIR="$BUILD_ROOT/spec"
WORK_DIR="$BUILD_ROOT/pyinstaller"
APP_NAME="TicketExamTrainer"
APP_BUNDLE="$DIST_ROOT/$APP_NAME.app"

echo "Building macOS app bundle into $APP_BUNDLE"

rm -rf "$APP_BUNDLE" "$WORK_DIR" "$SPEC_DIR"

"$PYTHON_EXE" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_ROOT" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  "$ROOT/main.py"

MACOS_ROOT="$APP_BUNDLE/Contents/MacOS"
mkdir -p "$MACOS_ROOT/app_data"

cp "$ROOT/README.md" "$MACOS_ROOT/README.md"

if [[ -d "$ROOT/docs" ]]; then
  rm -rf "$MACOS_ROOT/docs"
  cp -R "$ROOT/docs" "$MACOS_ROOT/docs"
fi

if [[ -d "$ROOT/scripts" ]]; then
  rm -rf "$MACOS_ROOT/scripts"
  cp -R "$ROOT/scripts" "$MACOS_ROOT/scripts"
fi

echo "Build completed: $APP_BUNDLE"
