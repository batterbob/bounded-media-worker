"""Child-only PDF parser operation."""

from __future__ import annotations

import io

from .types import LimitReason, Outcome


def extract(data: bytes, limits: object) -> dict[str, object]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        return {"outcome": Outcome.DEPENDENCY_UNAVAILABLE.value, "detail": "PDF support is not installed"}
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if len(reader.pages) > limits.max_pages:  # type: ignore[attr-defined]
            return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.PAGE_COUNT.value}
        parts: list[str] = []
        used = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            encoded = text.encode("utf-8")
            if used + len(encoded) > limits.max_text_bytes:  # type: ignore[attr-defined]
                return {"outcome": Outcome.OUTPUT_LIMIT.value, "limit_reason": LimitReason.TEXT_BYTES.value}
            parts.append(text)
            used += len(encoded)
        return {"outcome": Outcome.SUCCESS.value, "text": "\n".join(parts)}
    except (PdfReadError, OSError, ValueError):
        return {"outcome": Outcome.INVALID_INPUT.value, "detail": "PDF could not be parsed"}
