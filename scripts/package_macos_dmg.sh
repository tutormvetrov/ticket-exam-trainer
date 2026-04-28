#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXE="${TEZIS_PYTHON:-python3}"
APP_NAME="Tezis"
APP_BUNDLE="$ROOT/dist/$APP_NAME.app"
SEED_DB="data/state_exam_public_admin_demo.db"
BUILD_APP=0
SIGN_IDENTITY=""
ARCH_RAW="${TEZIS_RELEASE_ARCH:-$(uname -m)}"
VERSION_RAW="${TEZIS_PACKAGE_VERSION:-}"

usage() {
  cat <<'USAGE'
Package Tezis.app into a portable macOS DMG release asset.

Usage:
  bash scripts/package_macos_dmg.sh [options]

Options:
  --build                         Run scripts/build_mac_app.sh before packaging.
  --python PATH                   Python executable for version lookup and optional build.
  --seed-db PATH                  Seed DB passed to build_mac_app.sh when --build is used.
  --app PATH                      Existing .app bundle to package. Default: dist/Tezis.app.
  --arch arm64|x64|x86_64|universal
                                  Release architecture label. Default: current machine arch.
  --version VERSION               Release asset version. Default: app.meta APP_VERSION.
  --sign-identity IDENTITY        Optional codesign identity for the copied app in the DMG.
  -h, --help                      Show this help.

Output:
  dist/release/vX.Y.Z/macos/<arch>/Tezis-vX.Y.Z-macos-<arch>-portable.dmg
  dist/release/vX.Y.Z/checksums-vX.Y.Z.txt
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD_APP=1
      shift
      ;;
    --python)
      PYTHON_EXE="${2:?Missing value for --python}"
      shift 2
      ;;
    --seed-db)
      SEED_DB="${2:?Missing value for --seed-db}"
      shift 2
      ;;
    --app)
      APP_BUNDLE="${2:?Missing value for --app}"
      shift 2
      ;;
    --arch)
      ARCH_RAW="${2:?Missing value for --arch}"
      shift 2
      ;;
    --version)
      VERSION_RAW="${2:?Missing value for --version}"
      shift 2
      ;;
    --sign-identity)
      SIGN_IDENTITY="${2:?Missing value for --sign-identity}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS DMG packaging must run on macOS." >&2
  exit 1
fi

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "hdiutil not found. Run this script on macOS." >&2
  exit 1
fi

case "$ARCH_RAW" in
  arm64|aarch64)
    ARCH="arm64"
    ;;
  x86_64|amd64|x64)
    ARCH="x64"
    ;;
  universal|universal2)
    ARCH="universal"
    ;;
  *)
    echo "Unsupported arch '$ARCH_RAW'. Use arm64, x64, or universal." >&2
    exit 2
    ;;
esac

cd "$ROOT"

APP_VERSION="$("$PYTHON_EXE" -c 'from app.meta import APP_VERSION; print(APP_VERSION)')"
PACKAGE_VERSION="${VERSION_RAW:-$APP_VERSION}"
PACKAGE_VERSION="${PACKAGE_VERSION#v}"
RELEASE_ROOT="$ROOT/dist/release/v$PACKAGE_VERSION"
RELEASE_DIR="$RELEASE_ROOT/macos/$ARCH"
DMG_NAME="Tezis-v$PACKAGE_VERSION-macos-$ARCH-portable.dmg"
DMG_PATH="$RELEASE_DIR/$DMG_NAME"
STAGING_DIR="$ROOT/tmp-build-metadata/macos-dmg-$ARCH"
CHECKSUMS_PATH="$RELEASE_ROOT/checksums-v$PACKAGE_VERSION.txt"

if [[ "$BUILD_APP" -eq 1 ]]; then
  bash "$ROOT/scripts/build_mac_app.sh" "$PYTHON_EXE" "$SEED_DB"
fi

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "App bundle not found: $APP_BUNDLE" >&2
  echo "Run: bash scripts/build_mac_app.sh $PYTHON_EXE $SEED_DB" >&2
  echo "Or rerun this script with --build." >&2
  exit 1
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR" "$RELEASE_DIR"

echo "Copying app bundle into DMG staging area"
ditto "$APP_BUNDLE" "$STAGING_DIR/$APP_NAME.app"
ln -s /Applications "$STAGING_DIR/Applications"

if [[ -n "$SIGN_IDENTITY" ]]; then
  echo "Codesigning app with identity: $SIGN_IDENTITY"
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_IDENTITY" "$STAGING_DIR/$APP_NAME.app"
fi

SOURCE_SIZE_KB="$(du -sk "$STAGING_DIR" | awk '{print $1}')"
SOURCE_SIZE_MB=$(( (SOURCE_SIZE_KB + 1023) / 1024 ))
DMG_SIZE_MB=$(( SOURCE_SIZE_MB + 512 ))
if [[ "$DMG_SIZE_MB" -lt 1024 ]]; then
  DMG_SIZE_MB=1024
fi

FREE_SPACE_KB="$(df -Pk "$RELEASE_DIR" | awk 'NR == 2 {print $4}')"
REQUIRED_SPACE_KB=$(( (DMG_SIZE_MB * 1024) + SOURCE_SIZE_KB ))
if [[ "$FREE_SPACE_KB" -lt "$REQUIRED_SPACE_KB" ]]; then
  echo "Not enough free space for DMG packaging." >&2
  echo "Available: ${FREE_SPACE_KB} KB; required at least: ${REQUIRED_SPACE_KB} KB." >&2
  exit 1
fi

rm -f "$DMG_PATH"
echo "Creating DMG: $DMG_PATH"
echo "Staging size: ${SOURCE_SIZE_MB} MB; DMG filesystem capacity: ${DMG_SIZE_MB} MB"
hdiutil create \
  -volname "Tezis $APP_VERSION" \
  -srcfolder "$STAGING_DIR" \
  -size "${DMG_SIZE_MB}m" \
  -fs HFS+ \
  -ov \
  -format UDZO \
  "$DMG_PATH"

(
  cd "$RELEASE_ROOT"
  find . -type f \
    ! -name "checksums-v*.txt" \
    ! -name "*.sha256" \
    | LC_ALL=C sort \
    | while IFS= read -r artifact; do
        shasum -a 256 "$artifact"
      done
) > "$CHECKSUMS_PATH"

echo "DMG ready: $DMG_PATH"
echo "Checksums: $CHECKSUMS_PATH"
