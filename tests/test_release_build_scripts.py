from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_EXCLUDES = (
    "onnxruntime.quantization",
    "onnxruntime.tools",
    "onnxruntime.training",
    "onnxruntime.transformers",
    "accelerate",
    "datasets",
    "huggingface_hub",
    "pandas",
    "safetensors",
    "scipy",
    "sentence_transformers",
    "sklearn",
    "tokenizers",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
)


def test_windows_release_script_uses_non_build_workpath_for_build_info() -> None:
    script = (REPO_ROOT / "scripts" / "build_flet_exe.ps1").read_text(encoding="utf-8")

    assert 'tmp-build-metadata\\build_info.json' in script
    assert 'if ($BuildVersion)' in script
    assert 'if ($BuildCommit)' in script
    assert '"--pyinstaller-build-args=--exclude-module=$moduleName"' in script
    assert '"build\\build_info.json"' not in script
    for module_name in EXPECTED_EXCLUDES:
        assert f'"{module_name}"' in script


def test_macos_release_script_uses_non_build_workpath_for_build_info() -> None:
    script = (REPO_ROOT / "scripts" / "build_mac_app.sh").read_text(encoding="utf-8")

    assert 'tmp-build-metadata/build_info.json' in script
    assert 'if [[ -n "$BUILD_VERSION" ]]' in script
    assert 'if [[ -n "$BUILD_COMMIT" ]]' in script
    assert '--pyinstaller-build-args="--exclude-module=$module_name"' in script
    assert 'BUILD_INFO_PATH="$ROOT/build/build_info.json"' not in script
    for module_name in EXPECTED_EXCLUDES:
        assert f'"{module_name}"' in script


def test_macos_dmg_packaging_script_uses_release_tree_and_checksums() -> None:
    script = (REPO_ROOT / "scripts" / "package_macos_dmg.sh").read_text(encoding="utf-8")

    assert 'PACKAGE_VERSION="${VERSION_RAW:-$APP_VERSION}"' in script
    assert 'RELEASE_ROOT="$ROOT/dist/release/v$PACKAGE_VERSION"' in script
    assert 'DMG_NAME="Tezis-v$PACKAGE_VERSION-macos-$ARCH-portable.dmg"' in script
    assert "hdiutil create" in script
    assert 'DMG_SIZE_MB=$(( SOURCE_SIZE_MB + 512 ))' in script
    assert '-size "${DMG_SIZE_MB}m"' in script
    assert "-fs HFS+" in script
    assert 'ln -s /Applications "$STAGING_DIR/Applications"' in script
    assert 'CHECKSUMS_PATH="$RELEASE_ROOT/checksums-v$PACKAGE_VERSION.txt"' in script
    assert "shasum -a 256" in script
    assert 'bash "$ROOT/scripts/build_mac_app.sh" "$PYTHON_EXE" "$SEED_DB"' in script


def test_release_workflow_publishes_named_installers_portables_and_checksums() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'Tezis-Setup-$tag-windows-x64.exe' in workflow
    assert 'Tezis-$tag-windows-x64-portable.zip' in workflow
    assert 'Tezis-*-macos-${{ matrix.arch }}-portable.dmg' in workflow
    assert 'runner: macos-15' in workflow
    assert 'runner: macos-15-intel' in workflow
    assert 'package_macos_dmg.sh --build --python python3 --arch "${{ matrix.arch }}" --version "${{ github.ref_name }}"' in workflow
    assert 'sha256sum Tezis-* > "checksums-$tag.txt"' in workflow
    assert "fail_on_unmatched_files: true" in workflow
    assert "release-files/*.dmg" in workflow
    assert "release-files/checksums-*.txt" in workflow
