# bounded-media-worker

`bounded-media-worker` runs selected PDF and image operations in short-lived
child processes with explicit resource, protocol, and output limits. It provides
PDF text extraction, image OCR, and deterministic PNG canonicalization without
importing parser libraries into the parent process.

It is a resource-bounded worker, **not a security sandbox**. It does not prevent
network access, kernel or native-decoder defects, pre-exec blocking, or
uninterruptible process states. Use container or operating-system isolation
appropriate for hostile input.

Version `0.1.x` is a release-candidate API and may change before a stable release.

## Why use it?

Media parsers are useful but complex. Moving a parse into a child process gives
an application a smaller and more explicit failure boundary:

- input, output, text, page, pixel, dimension, and protocol sizes are bounded;
- CPU, address space, file size, and wall-clock time are limited;
- optional PDF/image/OCR dependencies import only in the child;
- requests and responses use a strict versioned JSON protocol;
- response reads are streamed and capped before retention;
- the worker runs in a fresh process group that is terminated and reaped on
  timeout or protocol overflow;
- results use conservative machine-readable outcomes instead of guessing why a
  process died;
- PNG canonicalization removes source metadata and emits deterministic RGB data.

```text
caller bytes + WorkerPolicy
            │
            ▼
  bounded parent protocol
            │ fresh child process group
            ▼
 parser imported after rlimits
            │
            ▼
 capped result or refusal outcome
```

## What it does not do

The package deliberately does not:

- provide a complete sandbox or container runtime;
- disable networking in the child;
- protect against kernel, interpreter, or native-library vulnerabilities;
- guarantee immediate teardown of a process stuck in kernel-uninterruptible
  sleep;
- accept caller-selected files, shell arguments, environment variables, or
  arbitrary Tesseract options;
- preserve image metadata, color profiles, animation, or source encoding;
- interpret extracted text or decide whether it is safe to trust.

## Requirements and installation

Linux/POSIX is required for the documented process-group and resource-limit
behavior. Python 3.11 or newer is supported.

The project is not currently published on PyPI. Download the wheel from the
immutable `v0.1.0-rc1` GitHub release, verify its published SHA-256 value, and
install the features you need locally:

```bash
python -m pip install './bounded_media_worker-0.1.0rc1-py3-none-any.whl[pdf]'

python -m pip install './bounded_media_worker-0.1.0rc1-py3-none-any.whl[image]'

python -m pip install './bounded_media_worker-0.1.0rc1-py3-none-any.whl[ocr]'
```

The base package has no parser dependency. The extras install:

| Extra | Operation | Dependency |
| --- | --- | --- |
| `pdf` | PDF text extraction | `pypdf` |
| `image` | PNG/JPEG canonicalization | Pillow |
| `ocr` | Image OCR | Pillow and `pytesseract` |

OCR also requires the `tesseract` system executable on the child `PATH`, or an
explicit executable path in `WorkerPolicy`. OCR uses a fixed page-segmentation
mode. Policy-provided language identifiers must be nonempty ASCII alphanumeric
names and cannot inject arbitrary Tesseract arguments.

## Quick start

### Extract bounded PDF text

```python
from bounded_media_worker import Outcome, WorkerPolicy, extract_pdf_text

result = extract_pdf_text(pdf_bytes, policy=WorkerPolicy())
if result.outcome is Outcome.SUCCESS:
    assert result.text is not None
    print(result.text)
else:
    print(result.outcome.value, result.limit_reason)
```

PDF page or text overflow returns no partial text.

### Canonicalize an image

```python
from bounded_media_worker import Outcome, WorkerPolicy, canonicalize_image

result = canonicalize_image(image_bytes, policy=WorkerPolicy())
if result.outcome is Outcome.SUCCESS:
    assert result.data is not None
    assert result.media_type == "image/png"
    canonical_png = result.data
```

`canonicalize_image` accepts PNG or JPEG input. It applies encoded orientation,
resizes within the configured dimensions, converts to RGB, and emits a PNG with
no text, EXIF, ICC, or ancillary source metadata.

### OCR an image

```python
from bounded_media_worker import Outcome, WorkerPolicy, ocr_image

policy = WorkerPolicy(ocr_languages=("eng",))
result = ocr_image(image_bytes, policy=policy)
if result.outcome is Outcome.SUCCESS:
    text = result.text or ""
```

## Policy and limits

`WorkerPolicy` contains immutable `WorkerLimits`. The defaults are conservative
starting points, not universal safe values:

| Limit | Default |
| --- | ---: |
| Input bytes | 8 MiB |
| Returned binary bytes | 2 MiB |
| Protocol frame bytes | 12 MiB |
| Extracted text bytes | 512 KiB |
| PDF pages | 64 |
| Image width/height | 8,000 pixels each |
| Image pixels | 24,000,000 |
| CPU time | 10 seconds |
| Address space | 768 MiB |
| Child file size | 8 MiB |
| Wall time | 15 seconds |

Applications can impose an `application_ceiling` so a request-specific policy
cannot exceed application-owned maxima:

```python
from bounded_media_worker import WorkerLimits, WorkerPolicy

ceiling = WorkerLimits(max_input_bytes=4 * 1024 * 1024)
policy = WorkerPolicy(
    limits=WorkerLimits(max_input_bytes=2 * 1024 * 1024),
    application_ceiling=ceiling,
)
```

All limits must be positive and internally consistent. Inputs that exceed
policy are rejected before the child starts.

## Outcomes and failure semantics

Operations return `TextResult` or `BytesResult`. Inspect `outcome` before using
payload fields:

| Outcome | Meaning |
| --- | --- |
| `success` | The complete bounded result is present |
| `invalid_input` | Input or request encoding violated policy |
| `dependency_unavailable` | The selected optional parser is unavailable |
| `protocol_error` | The child response violated the protocol |
| `timeout` | The wall-time deadline expired |
| `output_limit` | The bounded response frame overflowed |
| `worker_exit` | The worker failed, exited, or was signaled |
| `resource_terminated` | The child reported a resource-limit termination |

`limit_reason` provides a conservative category when one is known. A signal is
reported as `worker_exit`; the package does not claim that a particular CPU or
memory limit caused an otherwise ambiguous signal.

## Process boundary

The parent validates input size, encodes a strict request, and launches a fresh
Python process group with a minimal environment and `/` as its working directory.
The child applies CPU, address-space, and file-size limits before importing PDF,
image, or OCR libraries. No caller-provided paths, credentials, or environment
variables are forwarded.

The parent concurrently writes the request and reads the response with a single
wall-clock deadline. It never retains more than the configured protocol cap. On
timeout, overflow, or pipe failure it terminates the process group, waits a
bounded grace period, sends `SIGKILL`, and reaps the direct child.

There is still a small unavoidable window before the child installs limits.
Process-group teardown also cannot make a kernel-uninterruptible process vanish.
These are explicit reasons to combine the package with a stronger isolation
boundary for hostile or high-value workloads.

## Privacy and security boundaries

The package does not log input bytes or extracted contents and ships only
synthetic test material. Applications remain responsible for:

- authorization, consent, retention, and deletion;
- keeping documents and OCR text out of logs, traces, issues, and analytics;
- choosing stronger OS/container isolation where required;
- constraining network access outside this process helper;
- patching Python, parser dependencies, Tesseract, and the host operating system;
- treating all extracted content as untrusted data.

Report vulnerabilities through GitHub's private **Report a vulnerability**
form, not a public issue. See [SECURITY.md](SECURITY.md).

## Development and release verification

```bash
git clone <repository-url>
cd bounded-media-worker
python -m pip install -e ".[dev,pdf,image,ocr]"
python -m pytest
python -m ruff check src tests tools
python -m mypy src tools
python -m build
```

Release acceptance also uses a private denylist and scans tracked names and
contents, Git blobs, and wheel/sdist member names and contents. The scanner emits
only pass/fail receipts and never prints private terms or matching material.

See [CHANGELOG.md](CHANGELOG.md), the
[release-candidate report](docs/RELEASE_CANDIDATE.md), and
[provenance notes](docs/provenance.md) for the current candidate evidence.
