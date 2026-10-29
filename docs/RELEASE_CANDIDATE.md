# v0.1.0-rc1 release report

Candidate source commit: `3b76661ed25cce7354ee2aa2cd12ff7faaa49dfd`.

Release target: public GitHub release candidate; no PyPI publication.

Validated on Linux with Python 3.12:

- `pytest`: 37 passed
- Ruff and mypy: clean across package and release tools
- source tree vocabulary scan: clean
- `git fsck --no-dangling`: clean
- wheel and source distribution built from an isolated project environment
- fresh temporary installs succeeded for base, `pdf`, `image`, and `ocr` extras
- wheel `RECORD` hashes/sizes and source-distribution member structure: clean
- private denylist loaded without recording its contents; tracked names and
  contents, every Git blob, wheel, and source-distribution
  privacy/secret/PII receipts: PASS
- independent archive structure, wheel `RECORD`, byte-level source lineage,
  and clean-install review: PASS

Release artifacts:

| Artifact | SHA-256 |
| --- | --- |
| `bounded_media_worker-0.1.0rc1-py3-none-any.whl` | `323c69566d2018bf4c785f2e3e90b893f551f495dded28d7425329dc25b1f8c7` |
| `bounded_media_worker-0.1.0rc1.tar.gz` | `4d0be5cc3804add12e9ce3288aa1fdb7ca67558d91bd1487e670ab3a33fca31b` |

The host system Python lacks `ensurepip`, so an isolated project environment
was used for `build --no-isolation`; this is an environment constraint, not a
claim that the standard isolated build path passed.
