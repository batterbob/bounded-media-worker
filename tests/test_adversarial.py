from bounded_media_worker import Outcome, WorkerLimits, WorkerPolicy, extract_pdf_text


def test_protocol_bound_prevents_oversized_base64_request() -> None:
    policy = WorkerPolicy(limits=WorkerLimits(max_input_bytes=1, max_output_bytes=10, max_protocol_bytes=10))
    result = extract_pdf_text(b"x", policy=policy)
    assert result.outcome is Outcome.INVALID_INPUT
