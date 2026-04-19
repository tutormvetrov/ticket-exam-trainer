#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${1:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$ROOT/dist"
APP_NAME="Tezis"
APP_BUNDLE="$DIST_ROOT/$APP_NAME.app"
SEED_DB_INPUT="${TEZIS_SEED_DATABASE:-${2:-data/state_exam_public_admin_demo.db}}"
SEED_DB=""

if [[ -n "$SEED_DB_INPUT" ]]; then
  SEED_DB="$("$PYTHON_EXE" -c 'from app.release_seed import resolve_seed_database; import sys; print(resolve_seed_database(sys.argv[1]) or "")' "$SEED_DB_INPUT")"
fi

APP_VERSION="$("$PYTHON_EXE" -c 'from app.meta import APP_VERSION; print(APP_VERSION)')"
ICON_ARGS=()
ADD_DATA_ARGS=()

if [[ -f "$ROOT/assets/icon.icns" ]]; then
  ICON_ARGS+=(--icon "$ROOT/assets/icon.icns")
fi

if [[ -n "$SEED_DB" ]]; then
  ADD_DATA_ARGS+=(--add-data "$SEED_DB:data")
fi

if [[ -d "$ROOT/ui_flet/theme/fonts" ]]; then
  ADD_DATA_ARGS+=(--add-data "$ROOT/ui_flet/theme/fonts:ui_flet/theme/fonts")
fi

mkdir -p "$DIST_ROOT"
rm -rf "$APP_BUNDLE"

echo "Building macOS bundle into $APP_BUNDLE"
if [[ -n "$SEED_DB" ]]; then
  echo "Bundling seed database: $SEED_DB"
else
  echo "No seed database bundled"
fi

flet pack "$ROOT/ui_flet/main.py" \
  --name "$APP_NAME" \
  --distpath "$DIST_ROOT" \
  --product-name "Тезис" \
  --product-version "$APP_VERSION" \
  --bundle-id "com.tutormvetrov.tezis" \
  --copyright "2026" \
  --yes \
  "${ICON_ARGS[@]}" \
  "${ADD_DATA_ARGS[@]}"

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "Build failed: bundle not found at $APP_BUNDLE" >&2
  exit 1
fi

echo "Build completed: $APP_BUNDLE"
