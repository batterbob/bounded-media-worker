"""Resource-bounded media operations; this package is not a security sandbox."""

from .process import run_operation
from .types import BytesResult, LimitReason, Outcome, TextResult, WorkerLimits, WorkerPolicy


def extract_pdf_text(data: bytes, *, policy: WorkerPolicy) -> TextResult:
    return run_operation("pdf_text", data, policy, bytes_result=False)  # type: ignore[return-value]


def ocr_image(data: bytes, *, policy: WorkerPolicy) -> TextResult:
    return run_operation("image_ocr", data, policy, bytes_result=False)  # type: ignore[return-value]


def canonicalize_image(data: bytes, *, policy: WorkerPolicy) -> BytesResult:
    return run_operation("image_canonicalize", data, policy, bytes_result=True)  # type: ignore[return-value]


__all__ = ["BytesResult", "LimitReason", "Outcome", "TextResult", "WorkerLimits", "WorkerPolicy", "canonicalize_image", "extract_pdf_text", "ocr_image"]
