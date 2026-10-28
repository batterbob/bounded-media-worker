"""Child-only image validation, canonicalization, and OCR operations."""

from __future__ import annotations

import base64
import io
import os
import shutil
import struct
from typing import Any, cast

from .types import LimitReason, Outcome

_PNG = b"\x89PNG\r\n\x1a\n"
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _dimensions(data: bytes) -> tuple[str, int, int] | None:
    if data.startswith(_PNG) and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "PNG", width, height
    if not data.startswith(b"\xff\xd8"):
        return None
    position = 2
    while position + 9 <= len(data):
        if data[position] != 0xFF:
            return None
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return None
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(data):
            return None
        length = struct.unpack(">H", data[position:position + 2])[0]
        if length < 2 or position + length > len(data):
            return None
        if marker in _SOF and length >= 8:
            height, width = struct.unpack(">HH", data[position + 3:position + 7])
            return "JPEG", width, height
        position += length
    return None


def validate_header(data: bytes, limits: object) -> dict[str, object] | None:
    dimensions = _dimensions(data)
    if dimensions is None:
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "supported PNG or JPEG header required"}
    _, width, height = dimensions
    if width == 0 or height == 0:
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "zero image dimension"}
    if width > limits.max_image_width or height > limits.max_image_height:  # type: ignore[attr-defined]
        return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.IMAGE_DIMENSIONS.value}
    if width * height > limits.max_image_pixels:  # type: ignore[attr-defined]
        return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.IMAGE_PIXELS.value}
    return None


def _open(data: bytes) -> object | dict[str, object]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return {"outcome": Outcome.DEPENDENCY_UNAVAILABLE.value, "detail": "image support is not installed"}
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        return Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, ValueError):
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "image could not be decoded"}


def canonicalize(data: bytes, limits: object) -> dict[str, object]:
    failure = validate_header(data, limits)
    if failure:
        return failure
    image = _open(data)
    if isinstance(image, dict):
        return image
    try:
        from PIL import Image, ImageOps
        image = cast(Any, image)
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((limits.max_image_width, limits.max_image_height))  # type: ignore[attr-defined]
        canonical = Image.new("RGB", image.size)
        canonical.paste(image)
        output = io.BytesIO()
        canonical.save(output, format="PNG", optimize=False, compress_level=9, pnginfo=None, icc_profile=None, exif=b"")
        result = output.getvalue()
        if len(result) > limits.max_output_bytes:  # type: ignore[attr-defined]
            return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.OUTPUT_BYTES.value}
        return {"outcome": Outcome.SUCCESS.value, "data": base64.b64encode(result).decode("ascii"), "media_type": "image/png"}
    except (OSError, ValueError):
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "image canonicalization failed"}


def ocr(data: bytes, policy: object) -> dict[str, object]:
    failure = validate_header(data, policy.limits)  # type: ignore[attr-defined]
    if failure:
        return failure
    image = _open(data)
    if isinstance(image, dict):
        return image
    try:
        import pytesseract  # type: ignore[import-untyped]
    except ImportError:
        return {"outcome": Outcome.DEPENDENCY_UNAVAILABLE.value, "detail": "OCR support is not installed"}
    executable = policy.tesseract_path or "tesseract"  # type: ignore[attr-defined]
    resolved = executable if os.path.isabs(executable) else shutil.which(executable, path=os.defpath)
    if not resolved or not os.path.isfile(resolved) or not os.access(resolved, os.X_OK):
        return {"outcome": Outcome.DEPENDENCY_UNAVAILABLE.value, "detail": "Tesseract executable is unavailable"}
    try:
        image = cast(Any, image)
        pytesseract.pytesseract.tesseract_cmd = resolved
        text = pytesseract.image_to_string(image, lang="+".join(policy.ocr_languages), config="--psm 6")  # type: ignore[attr-defined]
        if len(text.encode("utf-8")) > policy.limits.max_text_bytes:  # type: ignore[attr-defined]
            return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.TEXT_BYTES.value}
        return {"outcome": Outcome.SUCCESS.value, "text": text}
    except (pytesseract.TesseractError, OSError, RuntimeError, ValueError):
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "OCR failed"}
