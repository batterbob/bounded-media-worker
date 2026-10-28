"""Public, immutable result and policy types."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    PROTOCOL_ERROR = "protocol_error"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    WORKER_EXIT = "worker_exit"
    RESOURCE_TERMINATED = "resource_terminated"


class LimitReason(str, Enum):
    INPUT_BYTES = "input_bytes"
    CPU_SECONDS = "cpu_seconds"
    ADDRESS_SPACE = "address_space"
    FILE_SIZE = "file_size"
    PAGE_COUNT = "page_count"
    TEXT_BYTES = "text_bytes"
    OUTPUT_BYTES = "output_bytes"
    IMAGE_DIMENSIONS = "image_dimensions"
    IMAGE_PIXELS = "image_pixels"
    WALL_TIME = "wall_time"
    PROTOCOL_BYTES = "protocol_bytes"


@dataclass(frozen=True, slots=True)
class WorkerLimits:
    """Limits applied to one request. Every value must be positive."""

    max_input_bytes: int = 8 * 1024 * 1024
    max_output_bytes: int = 2 * 1024 * 1024
    max_protocol_bytes: int = 12 * 1024 * 1024
    max_text_bytes: int = 512 * 1024
    max_pages: int = 64
    max_image_width: int = 8_000
    max_image_height: int = 8_000
    max_image_pixels: int = 24_000_000
    cpu_seconds: int = 10
    address_space_bytes: int = 768 * 1024 * 1024
    file_size_bytes: int = 8 * 1024 * 1024
    wall_time_seconds: float = 15.0

    def __post_init__(self) -> None:
        integer_fields = set(self.__dataclass_fields__) - {"wall_time_seconds"}
        if any(isinstance(getattr(self, field), bool) or not isinstance(getattr(self, field), int) for field in integer_fields):
            raise ValueError("non-wall-clock limits must be integers")
        if isinstance(self.wall_time_seconds, bool) or not isinstance(self.wall_time_seconds, (int, float)) or not math.isfinite(self.wall_time_seconds):
            raise ValueError("wall_time_seconds must be finite")
        if any(getattr(self, field) <= 0 for field in self.__dataclass_fields__):
            raise ValueError("all worker limits must be positive")
        if self.max_protocol_bytes < self.max_input_bytes:
            raise ValueError("max_protocol_bytes must cover max_input_bytes")
        if self.max_output_bytes > self.max_protocol_bytes:
            raise ValueError("max_output_bytes cannot exceed max_protocol_bytes")


@dataclass(frozen=True, slots=True)
class WorkerPolicy:
    limits: WorkerLimits = WorkerLimits()
    application_ceiling: WorkerLimits | None = None
    ocr_languages: tuple[str, ...] = ("eng",)
    tesseract_path: str | None = None

    def __post_init__(self) -> None:
        if not self.ocr_languages or any(not language.isascii() or not language.isalnum() for language in self.ocr_languages):
            raise ValueError("OCR languages must be nonempty ASCII alphanumeric names")
        if self.tesseract_path is not None and ("\x00" in self.tesseract_path or not self.tesseract_path):
            raise ValueError("tesseract_path must be a nonempty path when provided")
        ceiling = self.application_ceiling
        if ceiling is not None:
            for field in self.limits.__dataclass_fields__:
                if getattr(self.limits, field) > getattr(ceiling, field):
                    raise ValueError(f"limit {field} exceeds application ceiling")


@dataclass(frozen=True, slots=True)
class TextResult:
    outcome: Outcome
    text: str | None = None
    limit_reason: LimitReason | None = None
    signal: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class BytesResult:
    outcome: Outcome
    data: bytes | None = None
    media_type: str | None = None
    limit_reason: LimitReason | None = None
    signal: int | None = None
    detail: str | None = None
