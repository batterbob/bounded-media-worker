from bounded_media_worker import Outcome, WorkerLimits, WorkerPolicy, extract_pdf_text


def test_pdf_input_too_large_is_rejected() -> None:
    policy = WorkerPolicy(limits=WorkerLimits(max_input_bytes=4))
    assert extract_pdf_text(b"12345", policy=policy).outcome is Outcome.INVALID_INPUT


def test_generated_blank_pdf_runs_in_child() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    import io

    stream = io.BytesIO()
    writer.write(stream)
    result = extract_pdf_text(stream.getvalue(), policy=WorkerPolicy())
    assert result.outcome is Outcome.SUCCESS
    assert result.text == ""


def test_page_count_overflow_returns_no_partial_text() -> None:
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    stream = io.BytesIO()
    writer.write(stream)
    result = extract_pdf_text(stream.getvalue(), policy=WorkerPolicy(limits=WorkerLimits(max_pages=1)))
    assert result.outcome is Outcome.OUTPUT_LIMIT
    assert result.text is None
