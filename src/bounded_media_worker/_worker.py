"""Worker entry point. Parser imports remain inside operation modules."""

from __future__ import annotations

import base64
import binascii
import resource
import sys

from .policy import policy_from_wire
from .protocol import PROTOCOL_VERSION, ProtocolError, decode_frame, encode_frame
from .types import Outcome


def _limits(policy: object) -> None:
    limits = policy.limits  # type: ignore[attr-defined]
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (limits.address_space_bytes, limits.address_space_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_size_bytes, limits.file_size_bytes))


def _response(**values: object) -> dict[str, object]:
    return {"version": PROTOCOL_VERSION, **values}


def main() -> int:
    raw = sys.stdin.buffer.read(12 * 1024 * 1024 + 1)
    try:
        request = decode_frame(raw, maximum=12 * 1024 * 1024)
        if set(request) != {"version", "operation", "data", "policy"} or request["version"] != PROTOCOL_VERSION:
            raise ProtocolError("invalid request shape")
        if request["operation"] not in {"pdf_text", "image_ocr", "image_canonicalize"} or not isinstance(request["data"], str):
            raise ProtocolError("invalid request operation")
        policy = policy_from_wire(request["policy"])
        if len(raw) > policy.limits.max_protocol_bytes:
            raise ProtocolError("request exceeds policy")
        data = base64.b64decode(request["data"].encode("ascii"), validate=True)
        if len(data) > policy.limits.max_input_bytes:
            result: dict[str, object] = _response(outcome=Outcome.INVALID_INPUT.value, limit_reason="input_bytes")
        else:
            _limits(policy)
            if request["operation"] == "pdf_text":
                from .pdf import extract
                result = _response(**extract(data, policy.limits))
            elif request["operation"] == "image_ocr":
                from .image import ocr
                result = _response(**ocr(data, policy))
            else:
                from .image import canonicalize
                result = _response(**canonicalize(data, policy.limits))
    except (ProtocolError, ValueError, TypeError, binascii.Error):
        result = _response(outcome=Outcome.PROTOCOL_ERROR.value)
    except OSError:
        result = _response(outcome=Outcome.RESOURCE_TERMINATED.value)
    try:
        sys.stdout.buffer.write(encode_frame(result, maximum=12 * 1024 * 1024))
        sys.stdout.buffer.flush()
        return 0
    except OSError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
