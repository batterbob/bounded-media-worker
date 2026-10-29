"""Strict, one-frame JSON protocol used across the worker boundary."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from typing import Any

PROTOCOL_VERSION = 1


class ProtocolError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise ProtocolError("non-finite JSON number")


def decode_frame(raw: bytes, *, maximum: int) -> dict[str, Any]:
    if not raw or len(raw) > maximum:
        raise ProtocolError("invalid frame size")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ProtocolError, RecursionError) as error:
        raise ProtocolError("malformed JSON frame") from error
    if not isinstance(value, dict):
        raise ProtocolError("frame must be an object")
    if any(isinstance(item, float) and not math.isfinite(item) for item in _walk(value)):
        raise ProtocolError("non-finite JSON number")
    return value


def _walk(value: Any) -> Iterator[Any]:
    """Iterate JSON values without recursive traversal of hostile nesting."""
    pending = [value]
    while pending:
        item = pending.pop()
        yield item
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def encode_frame(value: dict[str, Any], *, maximum: int) -> bytes:
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > maximum:
        raise ProtocolError("response exceeds protocol bound")
    return raw
