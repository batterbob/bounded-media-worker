import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from bounded_media_worker import Outcome, WorkerLimits, WorkerPolicy, extract_pdf_text, process
from bounded_media_worker.process import _minimal_environment


def test_parent_environment_is_minimal() -> None:
    environment = _minimal_environment()
    assert set(environment) == {"PATH", "LANG", "LC_ALL", "PYTHONPATH"}
    assert "HOME" not in environment


def test_input_bound_is_checked_before_worker_start() -> None:
    result = extract_pdf_text(b"x" * 2, policy=WorkerPolicy(limits=WorkerLimits(max_input_bytes=1)))
    assert result.outcome is Outcome.INVALID_INPUT


def test_malformed_pdf_is_a_result_not_a_parent_exception() -> None:
    result = extract_pdf_text(b"not a PDF", policy=WorkerPolicy())
    assert result.outcome in {Outcome.INVALID_INPUT, Outcome.DEPENDENCY_UNAVAILABLE}


def test_timeout_terminates_the_worker_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    real_popen = subprocess.Popen
    script = "import os, sys, time; sys.stdin.buffer.read(); os.fork(); time.sleep(30)"

    def fake_popen(_args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(process.subprocess, "Popen", fake_popen)
    started = time.monotonic()
    result = extract_pdf_text(b"x", policy=WorkerPolicy(limits=WorkerLimits(wall_time_seconds=0.1)))
    assert result.outcome is Outcome.TIMEOUT
    assert time.monotonic() - started < 2


def test_timeout_kills_a_sigterm_resistant_grandchild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_popen = subprocess.Popen
    child_pid_file = tmp_path / "grandchild.pid"
    script = (
        "import os, signal, sys, time; "
        "sys.stdin.buffer.read(); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pid = os.fork(); "
        f"open({str(child_pid_file)!r}, 'w').write(str(pid) if pid else str(os.getpid())); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(30)"
    )

    def fake_popen(_args: object, **kwargs: Any) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(process.subprocess, "Popen", fake_popen)
    result = extract_pdf_text(b"x", policy=WorkerPolicy(limits=WorkerLimits(wall_time_seconds=0.1)))
    assert result.outcome is Outcome.TIMEOUT
    grandchild_pid = int(child_pid_file.read_text())
    for _ in range(20):
        try:
            os.kill(grandchild_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("SIGTERM-resistant grandchild survived process-group teardown")


def test_streaming_reader_rejects_excess_output() -> None:
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'x' * 32)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    with pytest.raises(process._OutputOverflow):
        process._communicate_bounded(child, b"", maximum=4, timeout=1)
    process._terminate_group(child)


def test_pipe_failure_becomes_conservative_worker_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_exchange(*_args: object, **_kwargs: object) -> bytes:
        raise BrokenPipeError

    monkeypatch.setattr(process, "_communicate_bounded", broken_exchange)
    result = extract_pdf_text(b"x", policy=WorkerPolicy())
    assert result.outcome is Outcome.WORKER_EXIT


def test_protocol_bootstrap_accepts_configured_limit_above_12_mebibytes() -> None:
    policy = WorkerPolicy(limits=WorkerLimits(max_input_bytes=10_000_000, max_protocol_bytes=15_000_000))
    result = extract_pdf_text(b"x" * 9_100_000, policy=policy)
    assert result.outcome is not Outcome.PROTOCOL_ERROR
