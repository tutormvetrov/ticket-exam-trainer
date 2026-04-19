from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import logging
from pathlib import Path
import re
from threading import Lock
from typing import Any

import requests
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


_LOG = logging.getLogger(__name__)

_OCR_MODEL_DIRNAME = "ocr_models"
_REQUEST_TIMEOUT_SECONDS = 120
_MIN_MEANINGFUL_IMAGE_AREA = 24_000
_MIN_MEANINGFUL_OCR_CHARS = 24
_WHITESPACE_RE = re.compile(r"\s+")

_CYRILLIC_REC_MODEL_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.8.0/"
    "onnx/PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile.onnx"
)
_CYRILLIC_REC_MODEL_SHA256 = "90f761b4bfcce0c8c561c0cb5c887b0971d3ec01c32164bdf7374a35b0982711"
_CYRILLIC_REC_KEYS_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.8.0/"
    "paddle/PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile/ppocrv5_cyrillic_dict.txt"
)
_CYRILLIC_REC_KEYS_SHA256 = "db40aa52ceb112055be80c694afdf655d5d2c4f7873704524cc16a447ca913ba"

_ENGINE_LOCK = Lock()
_ENGINE_CACHE: dict[str, RapidOCR] = {}


def resolve_ocr_cache_dir(workspace_root: Path | None = None) -> Path:
    base_dir = workspace_root or Path.cwd()
    return base_dir / "app_data" / _OCR_MODEL_DIRNAME


def is_meaningful_image(image_bytes: bytes, *, min_area: int = _MIN_MEANINGFUL_IMAGE_AREA) -> bool:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
    except Exception:
        return False
    return (width * height) >= min_area


def ocr_image_bytes(
    image_bytes: bytes,
    *,
    workspace_root: Path | None = None,
    min_chars: int = _MIN_MEANINGFUL_OCR_CHARS,
) -> str:
    if not image_bytes:
        return ""
    engine = _get_ocr_engine(resolve_ocr_cache_dir(workspace_root))
    result, _elapsed = engine(image_bytes)
    text = _normalize_ocr_text(_collect_ocr_text(result))
    if len(_comparison_text(text)) < min_chars:
        return ""
    return text


def should_keep_ocr_text(existing_text: str, ocr_text: str, *, min_chars: int = _MIN_MEANINGFUL_OCR_CHARS) -> bool:
    normalized_ocr = _comparison_text(ocr_text)
    if len(normalized_ocr) < min_chars:
        return False
    normalized_existing = _comparison_text(existing_text)
    return normalized_ocr not in normalized_existing


def _get_ocr_engine(cache_dir: Path) -> RapidOCR:
    cache_key = str(cache_dir.resolve())
    cached = _ENGINE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    with _ENGINE_LOCK:
        cached = _ENGINE_CACHE.get(cache_key)
        if cached is not None:
            return cached
        assets = _ensure_ocr_assets(cache_dir)
        engine = RapidOCR(
            print_verbose=False,
            text_score=0.35,
            rec_model_path=str(assets["rec_model"]),
            rec_keys_path=str(assets["rec_keys"]),
        )
        _ENGINE_CACHE[cache_key] = engine
        return engine


def _ensure_ocr_assets(cache_dir: Path) -> dict[str, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    rec_model = cache_dir / "cyrillic_PP-OCRv5_rec_mobile.onnx"
    rec_keys = cache_dir / "ppocrv5_cyrillic_dict.txt"
    _ensure_download(rec_model, _CYRILLIC_REC_MODEL_URL, _CYRILLIC_REC_MODEL_SHA256)
    _ensure_download(rec_keys, _CYRILLIC_REC_KEYS_URL, _CYRILLIC_REC_KEYS_SHA256)
    return {"rec_model": rec_model, "rec_keys": rec_keys}


def _ensure_download(target_path: Path, url: str, expected_sha256: str) -> None:
    if target_path.exists() and _file_sha256(target_path) == expected_sha256:
        return

    _LOG.info("Downloading OCR asset target=%s", target_path)
    response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS, stream=True)
    response.raise_for_status()

    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with response:
        with tmp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    actual_sha256 = _file_sha256(tmp_path)
    if actual_sha256 != expected_sha256:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"OCR asset checksum mismatch for {target_path.name}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    tmp_path.replace(target_path)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_ocr_text(result: Any) -> str:
    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        text = ""
        if isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[1], str):
                text = item[1]
            elif item and isinstance(item[0], str):
                text = item[0]
        if text:
            lines.append(str(text).strip())
    return "\n".join(lines)


def _normalize_ocr_text(text: str) -> str:
    normalized_lines: list[str] = []
    for raw_line in text.splitlines():
        line = _WHITESPACE_RE.sub(" ", raw_line).strip(" |")
        if len(line) < 2:
            continue
        if normalized_lines and normalized_lines[-1] == line:
            continue
        normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


def _comparison_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").lower()).strip()
