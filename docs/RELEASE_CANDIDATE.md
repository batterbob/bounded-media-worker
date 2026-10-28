# v0.1.0-rc1 local candidate report

Candidate commit: `12368d4`.

Validated on Linux with Python 3.12:

- `pytest`: 17 passed
- Ruff and mypy: clean
- source tree vocabulary scan: clean
- `git fsck --no-dangling`: clean
- wheel and source distribution built from an isolated project environment
- fresh temporary installs succeeded for base, `pdf`, `image`, and `ocr` extras

Current artifacts are local only in `release-artifacts-rc1-r2/`:

| Artifact | SHA-256 |
| --- | --- |
| `bounded_media_worker-0.1.0rc1-py3-none-any.whl` | `903ffd6fff0f32a3e39ed09bbd712eef36866c7a48e706f9320e061ba08f08ef` |
| `bounded_media_worker-0.1.0rc1.tar.gz` | `6c9119d4ffb30c1e8e29ce2038304389c8b74c3dfb03a1185656238ce0db913f` |

The host system Python lacks `ensurepip`, so an isolated project environment
was used for `build --no-isolation`; this is an environment constraint, not a
claim that the standard isolated build path passed. No tag, remote, push, or
publication was created. Independent archive review remains required before any
publication decision.
