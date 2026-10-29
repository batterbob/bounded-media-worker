"""Parent-side worker launch, timeout, and process-group cleanup."""

from __future__ import annotations

import base64
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .policy import policy_to_wire, validate_data
from .protocol import PROTOCOL_VERSION, ProtocolError, decode_frame, encode_frame
from .types import BytesResult, LimitReason, Outcome, TextResult, WorkerPolicy

_DETAIL_CAP = 512


class _OutputOverflow(Exception):
    pass


def _minimal_environment() -> dict[str, str]:
    package_root = str(Path(__file__).resolve().parents[1])
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONPATH": package_root}


def _result_from_wire(
    value: dict[str, Any], *, operation: str, policy: WorkerPolicy
) -> TextResult | BytesResult:
    allowed = {"version", "outcome", "limit_reason", "signal", "detail", "text", "data", "media_type"}
    if set(value) - allowed or value.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("invalid response shape")
    try:
        outcome = Outcome(value["outcome"])
    except (KeyError, ValueError) as error:
        raise ProtocolError("invalid response enum") from error
    if "limit_reason" in value:
        try:
            reason = LimitReason(value["limit_reason"])
        except (TypeError, ValueError) as error:
            raise ProtocolError("invalid response enum") from error
    else:
        reason = None
    signal_value = value.get("signal")
    detail = value.get("detail")
    if signal_value is not None and (isinstance(signal_value, bool) or not isinstance(signal_value, int)):
        raise ProtocolError("invalid signal")
    if detail is not None and (not isinstance(detail, str) or len(detail.encode()) > _DETAIL_CAP):
        raise ProtocolError("invalid detail")
    text_operation = operation in {"pdf_text", "image_ocr"}
    if not text_operation and operation != "image_canonicalize":
        raise ProtocolError("invalid operation")
    payload_fields = {"text", "data", "media_type"}
    if outcome is not Outcome.SUCCESS:
        if payload_fields & set(value):
            raise ProtocolError("non-success response contains payload")
        return (TextResult if text_operation else BytesResult)(outcome, limit_reason=reason, signal=signal_value, detail=detail)
    if reason is not None or signal_value is not None or detail is not None:
        raise ProtocolError("success response contains failure metadata")
    if text_operation:
        if set(value) != {"version", "outcome", "text"} or not isinstance(value["text"], str):
            raise ProtocolError("invalid text success response")
        text = value["text"]
        if len(text.encode()) > policy.limits.max_text_bytes:
            return TextResult(Outcome.OUTPUT_LIMIT, limit_reason=LimitReason.TEXT_BYTES)
        return TextResult(Outcome.SUCCESS, text)
    if set(value) != {"version", "outcome", "data", "media_type"}:
        raise ProtocolError("invalid binary success response")
    encoded = value["data"]
    if not isinstance(encoded, str) or value["media_type"] != "image/png":
        raise ProtocolError("invalid binary success response")
    try:
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise ProtocolError("invalid response data") from error
    if len(data) > policy.limits.max_output_bytes:
        return BytesResult(Outcome.OUTPUT_LIMIT, limit_reason=LimitReason.OUTPUT_BYTES)
    return BytesResult(Outcome.SUCCESS, data, "image/png")


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
            [sys.executable, "-m", "bounded_media_worker._worker", str(policy.limits.max_protocol_bytes)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=_minimal_environment(), cwd="/", start_new_session=True,
        )
    except OSError:
        return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT, detail="worker could not start")
    normal_complete = False
    try:
        try:
            stdout, returncode = _communicate_bounded(
                child, frame, policy.limits.max_protocol_bytes, policy.limits.wall_time_seconds
            )
            normal_complete = True
        except TimeoutError:
            return (BytesResult if bytes_result else TextResult)(Outcome.TIMEOUT, limit_reason=LimitReason.WALL_TIME)
        except _OutputOverflow:
            return (BytesResult if bytes_result else TextResult)(Outcome.OUTPUT_LIMIT, limit_reason=LimitReason.PROTOCOL_BYTES)
        except (OSError, RuntimeError, ValueError):
            return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT)
        if returncode < 0:
            return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT, signal=-returncode)
        if returncode:
            return (BytesResult if bytes_result else TextResult)(Outcome.WORKER_EXIT)
        try:
            return _result_from_wire(
                decode_frame(stdout, maximum=policy.limits.max_protocol_bytes), operation=operation, policy=policy
            )
        except (ProtocolError, ValueError, RecursionError):
            return (BytesResult if bytes_result else TextResult)(Outcome.PROTOCOL_ERROR)
    finally:
        _terminate_group(child, normal_complete=normal_complete)


def _terminate_group(child: subprocess.Popen[bytes], *, normal_complete: bool = False) -> None:
    """Terminate the session before reaping its leader, which pins its PGID."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except OSError:
        pass
    if not normal_complete:
        time.sleep(0.5)
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        child.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _communicate_bounded(
    child: subprocess.Popen[bytes], request: bytes, maximum: int, timeout: float
) -> tuple[bytes, int]:
    """Exchange one frame without retaining more than ``maximum`` response bytes."""
    if child.stdin is None or child.stdout is None:
        raise RuntimeError("worker pipes are unavailable")
    deadline = time.monotonic() + timeout
    written = 0
    output = bytearray()
    with selectors.DefaultSelector() as selector:
        os.set_blocking(child.stdin.fileno(), False)
        os.set_blocking(child.stdout.fileno(), False)
        selector.register(child.stdin, selectors.EVENT_WRITE)
        selector.register(child.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            for key, _ in selector.select(remaining):
                if key.fileobj is child.stdin:
                    try:
                        written += os.write(child.stdin.fileno(), request[written:])
                    except BlockingIOError:
                        continue
                    if written == len(request):
                        selector.unregister(child.stdin)
                        child.stdin.close()
                else:
                    try:
                        chunk = os.read(child.stdout.fileno(), min(65_536, maximum + 1 - len(output)))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(child.stdout)
                        child.stdout.close()
                    else:
                        output.extend(chunk)
                        if len(output) > maximum:
                            raise _OutputOverflow
    return bytes(output), _observe_exit_without_reaping(child, deadline)


def _observe_exit_without_reaping(child: subprocess.Popen[bytes], deadline: float) -> int:
    """Observe child exit while retaining its zombie leader until group cleanup."""
    flags = os.WEXITED | os.WNOHANG | os.WNOWAIT
    while True:
        try:
            info = os.waitid(os.P_PID, child.pid, flags)
        except (ChildProcessError, OSError) as error:
            raise RuntimeError("worker exit could not be observed") from error
        if info is not None:
            if info.si_code == os.CLD_EXITED:
                return info.si_status
            if info.si_code in {os.CLD_KILLED, os.CLD_DUMPED}:
                return -info.si_status
            raise RuntimeError("worker returned an unexpected wait status")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        time.sleep(min(0.01, remaining))
