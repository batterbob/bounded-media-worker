"""Reject known private-source vocabulary in release inputs."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DENYLIST = ("dailybrief", "homer", "parentvue", "hermes")
SELF = pathlib.Path(__file__).resolve()


def main() -> int:
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        if (
            path == SELF
            or not path.is_file()
            or {".git", ".venv", "dist", "build"}.intersection(path.parts)
            or path.suffix in {".pyc", ".png", ".jpg", ".whl", ".gz"}
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8").casefold()
        except UnicodeDecodeError:
            continue
        if any(word in text for word in DENYLIST):
            bad.append(str(path.relative_to(ROOT)))
    if bad:
        print("private vocabulary found: " + ", ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
