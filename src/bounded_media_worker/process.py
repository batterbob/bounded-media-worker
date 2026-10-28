"""Parent-side worker launch, timeout, and process-group cleanup."""

from __future__ import annotations

import base64
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .policy import policy_to_wire, validate_data
from .protocol import PROTOCOL_VERSION, ProtocolError, decode_frame, encode_frame
from .types import BytesResult, LimitReason, Outcome, TextResult, WorkerPolicy

_DETAIL_CAP = 512


def _minimal_environment() -> dict[str, str]:
    package_root = str(Path(__file__).resolve().parents[1])
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONPATH": package_root}


def _result_from_wire(value: dict[str, Any], *, bytes_result: bool) -> TextResult | BytesResult:
    allowed = {"version", "outcome", "limit_reason", "signal", "detail", "text", "data", "media_type"}
    if set(value) - allowed or value.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("invalid response shape")
    try:
        outcome = Outcome(value["outcome"])
        reason = LimitReason(value["limit_reason"]) if value.get("limit_reason") else None
    except (KeyError, ValueError) as error:
        raise ProtocolError("invalid response enum") from error
    signal_value = value.get("signal")
    detail = value.get("detail")
    if signal_value is not None and (isinstance(signal_value, bool) or not isinstance(signal_value, int)):
        raise ProtocolError("invalid signal")
    if detail is not None and (not isinstance(detail, str) or len(detail.encode()) > _DETAIL_CAP):
        raise ProtocolError("invalid detail")
    if bytes_result:
        encoded = value.get("data")
        data = None
        if encoded is not None:
            if not isinstance(encoded, str):
                raise ProtocolError("invalid response data")
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        media_type = value.get("media_type")
        if media_type is not None and not isinstance(media_type, str):
            raise ProtocolError("invalid media type")
        return BytesResult(outcome, data, media_type, reason, signal_value, detail)
    text = value.get("text")
    if text is not None and not isinstance(text, str):
        raise ProtocolError("invalid response text")
    return TextResult(outcome, text, reason, signal_value, detail)


def run_operation(operation: str, data: bytes, policy: WorkerPolicy, *, bytes_result: bool) -> TextResult | BytesResult:
    try:
        validate_data(data, policy)
    except TypeError:
        return (BytesResult if bytes_result else TextResult)(Outcome.INVALID_INPUT, detail="data must be bytes")
    except ValueError:
        return (BytesResult if bytes_result else TextResult)(Outcome.INVALID_INPUT, limit_reason=LimitReason.INPUT_BYTES)
    request = {"version": PROTOCOL_VERSION, "operation": operation, "data": base64.b64encode(data).decode("ascii"), "policy": policy_to_wire(policy)}
    try:
        frame = encode_frame(request, maximum=policy.limits.max_protocol_bytes)
    except ProtocolError:
        return (BytesResult if bytes_result else TextResult)(Outcome.INVALID_INPUT, limit_reason=LimitReason.PROTOCOL_BYTES)
    try:
        child = subprocess.Popen(
            [sys.executable, "-m", "bounded_media_worker._worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=_minimal_environment(), cwd="/", start_new_session=True,
        )
    except OSError:
        return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT, detail="worker could not start")
    try:
        stdout, _ = child.communicate(frame, timeout=policy.limits.wall_time_seconds)
    except subprocess.TimeoutExpired:
        _terminate_group(child)
        return (BytesResult if bytes_result else TextResult)(Outcome.TIMEOUT, limit_reason=LimitReason.WALL_TIME)
    if child.returncode is not None and child.returncode < 0:
        return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT, signal=-child.returncode)
    if child.returncode:
        return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT)
    try:
        return _result_from_wire(decode_frame(stdout, maximum=policy.limits.max_protocol_bytes), bytes_result=bytes_result)
    except (ProtocolError, ValueError):
        return (BytesResult if bytes_result else TextResult)(Outcome.PROTOCOL_ERROR)


def _terminate_group(child: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=0.5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait(timeout=1.0)
