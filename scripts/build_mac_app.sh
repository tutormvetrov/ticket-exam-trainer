#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${1:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$ROOT/dist"
BUILD_ROOT="$ROOT/build"
SPEC_DIR="$BUILD_ROOT/spec"
WORK_DIR="$BUILD_ROOT/pyinstaller"
APP_NAME="Tezis"
APP_BUNDLE="$DIST_ROOT/$APP_NAME.app"
BUILD_INFO_PATH="$APP_BUNDLE/Contents/MacOS/build_info.json"
SEED_DB_INPUT="${TEZIS_SEED_DATABASE:-${2:-}}"
SEED_DB=""
LOGO_ASSETS="$ROOT/assets/logo"
if [[ -n "$SEED_DB_INPUT" ]]; then
  SEED_DB="$("$PYTHON_EXE" -c 'from app.release_seed import resolve_seed_database; import sys; resolved = resolve_seed_database(sys.argv[1]); print(resolved if resolved is not None else "")' "$SEED_DB_INPUT")"
fi
APP_VERSION="$("$PYTHON_EXE" -c 'from app.meta import APP_VERSION; print(APP_VERSION)')"
APP_ARCHIVE="$DIST_ROOT/$APP_NAME-macos.zip"

echo "Building macOS app bundle into $APP_BUNDLE"
if [[ -n "$SEED_DB" ]]; then
  echo "Bundling explicit seed database: $SEED_DB"
else
  echo "No seed database requested; app bundle will create exam_trainer.db in the user workspace on first launch."
fi

rm -rf "$APP_BUNDLE" "$WORK_DIR" "$SPEC_DIR" "$APP_ARCHIVE"

"$PYTHON_EXE" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_ROOT" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  --add-data "$LOGO_ASSETS:assets/logo" \
  "$ROOT/main.py"

MACOS_ROOT="$APP_BUNDLE/Contents/MacOS"
mkdir -p "$MACOS_ROOT/app_data"

if [[ -n "$SEED_DB" ]]; then
  cp "$SEED_DB" "$MACOS_ROOT/exam_trainer.db"
  echo "Bundled seeded database: $SEED_DB"
fi

cp "$ROOT/README.md" "$MACOS_ROOT/README.md"

if [[ -d "$ROOT/docs" ]]; then
  rm -rf "$MACOS_ROOT/docs"
  cp -R "$ROOT/docs" "$MACOS_ROOT/docs"
fi

if [[ -d "$ROOT/scripts" ]]; then
  rm -rf "$MACOS_ROOT/scripts"
  cp -R "$ROOT/scripts" "$MACOS_ROOT/scripts"
fi

GIT_COMMIT="$(git -C "$ROOT" rev-parse --short=12 HEAD 2>/dev/null || true)"
cat > "$BUILD_INFO_PATH" <<EOF
{
  "version": "$APP_VERSION",
  "commit": "$GIT_COMMIT",
  "built_at": "$(date -Iseconds)"
}
EOF

echo "Build completed: $APP_BUNDLE"
(
  cd "$DIST_ROOT"
  zip -qry "$APP_ARCHIVE" "$APP_NAME.app"
)
echo "Release archive updated: $APP_ARCHIVE"
