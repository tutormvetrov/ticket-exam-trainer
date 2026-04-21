#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${1:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$ROOT/dist"
APP_NAME="Tezis"
APP_BUNDLE="$DIST_ROOT/$APP_NAME.app"
SEED_DB_INPUT="${TEZIS_SEED_DATABASE:-${2:-data/state_exam_public_admin_demo.db}}"
SEED_DB=""
BUILD_INFO_RELATIVE_PATH="tmp-build-metadata/build_info.json"
BUILD_INFO_PATH="$ROOT/$BUILD_INFO_RELATIVE_PATH"
BUILD_VERSION="${TEZIS_BUILD_VERSION:-}"
BUILD_COMMIT="${TEZIS_BUILD_COMMIT:-}"
EXCLUDED_MODULES=(
  # OCR uses onnxruntime inference only; these helper namespaces drag in
  # transformers/torch/scipy/pandas toolchains from the local environment.
  "onnxruntime.quantization"
  "onnxruntime.tools"
  "onnxruntime.training"
  "onnxruntime.transformers"
  # The app does not use these ML stacks directly. If they are installed in the
  # build environment, PyInstaller may otherwise pull gigabytes of baggage.
  "accelerate"
  "datasets"
  "huggingface_hub"
  "pandas"
  "safetensors"
  "scipy"
  "sentence_transformers"
  "sklearn"
  "tokenizers"
  "torch"
  "torchaudio"
  "torchvision"
  "transformers"
)

cd "$ROOT"

if [[ -n "$SEED_DB_INPUT" ]]; then
  SEED_DB="$("$PYTHON_EXE" -c 'from app.release_seed import resolve_seed_database; import sys; print(resolve_seed_database(sys.argv[1]) or "")' "$SEED_DB_INPUT")"
fi

APP_VERSION="$("$PYTHON_EXE" -c 'from app.meta import APP_VERSION; print(APP_VERSION)')"
ICON_ARGS=()
ADD_DATA_ARGS=()
BUILD_INFO_ARGS=("$ROOT/scripts/write_build_info.py" --output "$BUILD_INFO_PATH")
PYINSTALLER_BUILD_ARGS=()

if [[ -f "$ROOT/assets/icon.icns" ]]; then
  ICON_ARGS+=(--icon "$ROOT/assets/icon.icns")
fi

if [[ -n "$SEED_DB" ]]; then
  ADD_DATA_ARGS+=(--add-data "$SEED_DB:data")
fi

if [[ -d "$ROOT/ui_flet/theme/fonts" ]]; then
  ADD_DATA_ARGS+=(--add-data "$ROOT/ui_flet/theme/fonts:ui_flet/theme/fonts")
fi

if [[ -n "$BUILD_VERSION" ]]; then
  BUILD_INFO_ARGS+=(--version "$BUILD_VERSION")
fi

if [[ -n "$BUILD_COMMIT" ]]; then
  BUILD_INFO_ARGS+=(--commit "$BUILD_COMMIT")
fi

"$PYTHON_EXE" "${BUILD_INFO_ARGS[@]}"
ADD_DATA_ARGS+=(--add-data "$BUILD_INFO_RELATIVE_PATH:.")
for module_name in "${EXCLUDED_MODULES[@]}"; do
  PYINSTALLER_BUILD_ARGS+=(--pyinstaller-build-args="--exclude-module=$module_name")
done

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
  "${PYINSTALLER_BUILD_ARGS[@]}" \
  ${ICON_ARGS[@]+"${ICON_ARGS[@]}"} \
  ${ADD_DATA_ARGS[@]+"${ADD_DATA_ARGS[@]}"}

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "Build failed: bundle not found at $APP_BUNDLE" >&2
  exit 1
fi

echo "Build completed: $APP_BUNDLE"
