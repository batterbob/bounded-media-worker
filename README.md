# bounded-media-worker

`bounded-media-worker` runs selected PDF and image operations in short-lived child processes with explicit resource limits. It offers PDF text extraction, image OCR, and deterministic PNG canonicalization.

It is a resource-bounded worker, **not a security sandbox**. It does not prevent network access, kernel or decoder defects, pre-exec blocking, or uninterruptible process states. Use a container or operating-system isolation appropriate for hostile input.

## Requirements

Linux/POSIX is required for the documented process-group and resource-limit behavior. Python 3.11+ is supported. Install the relevant optional feature:

```bash
python -m pip install 'bounded-media-worker[pdf]'
python -m pip install 'bounded-media-worker[image]'
python -m pip install 'bounded-media-worker[ocr]'
```

OCR also requires the `tesseract` system executable on the child `PATH`, or an explicit executable path in `WorkerPolicy`. OCR uses a fixed page-segmentation mode and accepts only policy-provided alphanumeric language identifiers; callers cannot supply arbitrary Tesseract arguments.

## API

```python
from bounded_media_worker import WorkerPolicy, extract_pdf_text

result = extract_pdf_text(pdf_bytes, policy=WorkerPolicy())
if result.outcome.value == "success":
    print(result.text)
```

`canonicalize_image` accepts PNG/JPEG input and produces metadata-free RGB PNG. It applies orientation, then resizes within the policy dimensions. PDF page and text overflow return no partial text. All results report a conservative `Outcome`; a signal is reported as `WORKER_EXIT` and is not attributed to CPU or memory exhaustion.

## Boundary and failure semantics

The parent validates input size, sends a versioned bounded JSON request over standard input, creates a fresh process group, and kills/reaps that group on wall timeout. The child sets CPU, address-space, and file-size limits before importing parser libraries. It receives a minimal environment and no caller-provided paths or credentials. Output, text, pixels, dimensions, pages, and protocol frames are bounded. Parser dependencies remain optional and import only in the child.

The small unavoidable pre-exec window, native decoder risk, D-state processes, and the absence of a networking guarantee are intentional non-goals. A timeout tries process-group termination followed by a bounded kill/reap sequence; a kernel-uninterruptible child cannot be guaranteed to disappear immediately.

## Development

Run `python -m pytest`, `ruff check src tests`, `mypy src`, and `python -m build`. `tools/check_release_tree.py` rejects known private-source vocabulary before a release artifact is accepted.
