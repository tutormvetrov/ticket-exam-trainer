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
