# v0.1.0-rc1 local candidate report

Candidate commit: `a8391940bb48c003aa09da106f9b0bca2fe645f0`.

Validated on Linux with Python 3.12:

- `pytest`: 23 passed
- Ruff and mypy: clean across package, tests, and release tools
- source tree vocabulary scan: clean
- `git fsck --no-dangling`: clean
- wheel and source distribution built from an isolated project environment
- fresh temporary installs succeeded for base, `pdf`, `image`, and `ocr` extras
- wheel `RECORD` hashes/sizes and source-distribution member structure: clean
- private denylist loaded without recording its contents; source, Git-object,
  wheel, and source-distribution privacy/secret/PII receipts: PASS

Current artifacts are local only in `release-artifacts-rc1-r4/`:

| Artifact | SHA-256 |
| --- | --- |
| `bounded_media_worker-0.1.0rc1-py3-none-any.whl` | `34297a4c6f7f0781eed702a00be5231260cddcc4732a158eaefa2630dab365e3` |
| `bounded_media_worker-0.1.0rc1.tar.gz` | `eb12acb8c669e6e299dd849d73f6a50fb1fb4a47d8a67e284c2f2f1123318e29` |

The host system Python lacks `ensurepip`, so an isolated project environment
was used for `build --no-isolation`; this is an environment constraint, not a
claim that the standard isolated build path passed. No tag, remote, push, or
publication was created. Independent archive review remains required before any
publication decision.
