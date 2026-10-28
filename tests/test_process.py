from bounded_media_worker import Outcome, WorkerLimits, WorkerPolicy, extract_pdf_text
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
