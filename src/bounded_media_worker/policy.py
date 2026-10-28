"""Policy serialization and input validation shared by the parent and child."""

from __future__ import annotations

from typing import Any

from .types import WorkerLimits, WorkerPolicy


def policy_to_wire(policy: WorkerPolicy) -> dict[str, Any]:
    return {
        "limits": {field: getattr(policy.limits, field) for field in policy.limits.__dataclass_fields__},
        "ocr_languages": list(policy.ocr_languages),
        "tesseract_path": policy.tesseract_path,
    }


def policy_from_wire(value: object) -> WorkerPolicy:
    if not isinstance(value, dict) or set(value) != {"limits", "ocr_languages", "tesseract_path"}:
        raise ValueError("invalid policy shape")
    limits_value = value["limits"]
    if not isinstance(limits_value, dict) or set(limits_value) != set(WorkerLimits.__dataclass_fields__):
        raise ValueError("invalid limits shape")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in limits_value.values()):
        raise ValueError("limits must be numeric")
    languages = value["ocr_languages"]
    path = value["tesseract_path"]
    if not isinstance(languages, list) or not all(isinstance(item, str) for item in languages):
        raise ValueError("invalid OCR languages")
    if path is not None and not isinstance(path, str):
        raise ValueError("invalid tesseract path")
    return WorkerPolicy(limits=WorkerLimits(**limits_value), ocr_languages=tuple(languages), tesseract_path=path)


def validate_data(data: bytes, policy: WorkerPolicy) -> None:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if len(data) > policy.limits.max_input_bytes:
        raise ValueError("input exceeds policy")
