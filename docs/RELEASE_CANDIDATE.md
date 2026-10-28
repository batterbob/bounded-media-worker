# v0.1.0-rc1 local candidate report

Candidate commit: `822e1f66c6f494a6248ec8b8dd01ff950d9749db`.

Validated on Linux with Python 3.12:

- `pytest`: 20 passed
- Ruff and mypy: clean
- source tree vocabulary scan: clean
- `git fsck --no-dangling`: clean
- wheel and source distribution built from an isolated project environment
- fresh temporary installs succeeded for base, `pdf`, `image`, and `ocr` extras

Current artifacts are local only in `release-artifacts-rc1-r3/`:

| Artifact | SHA-256 |
| --- | --- |
| `bounded_media_worker-0.1.0rc1-py3-none-any.whl` | `350029090fc932d3ee6e1313d07082f275fdf50af39c7480ed933c5b5eb6f5a8` |
| `bounded_media_worker-0.1.0rc1.tar.gz` | `b55cecf427664c7c3c9be7fe38c40fd3e04fae0ab85e09c0d35ceef7486d2794` |

The host system Python lacks `ensurepip`, so an isolated project environment
was used for `build --no-isolation`; this is an environment constraint, not a
claim that the standard isolated build path passed. No tag, remote, push, or
publication was created. Independent archive review remains required before any
publication decision.
