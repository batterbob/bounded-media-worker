"""Run private-denylist, generic-secret, and PII scans without printing matches."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import math
import re
import subprocess
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
_CREDENTIAL_LABELS = (
    ("a" "pi[_-]?k" "ey"),
    ("s" "ec" "ret"),
    ("t" "ok" "en"),
    ("p" "ass" "word"),
    ("p" "rivate[_-]?k" "ey"),
)
SECRET_ASSIGNMENT = re.compile(r"(?i)(?:" + "|".join(_CREDENTIAL_LABELS) + r")\s*[:=]\s*[\"']?[^\s\"']{8,}")
LONG_TEXT = re.compile(r"[A-Za-z0-9+/=_-]{32,}")
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")


class GateFailure(Exception):
    pass


def _denylist(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GateFailure from error
    terms = tuple(
        line.strip().casefold()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and any(character.isalnum() for character in line)
    )
    if not terms:
        raise GateFailure
    return terms


def _entropy(value: str) -> float:
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in map(value.count, set(value)))


def _contains_prohibited(content: bytes, terms: tuple[str, ...]) -> bool:
    text = content.decode("utf-8", "ignore").casefold()
    if any(_term_matches(text, term) for term in terms):
        return True
    if SECRET_ASSIGNMENT.search(text) or EMAIL.search(text):
        return True
    for token in LONG_TEXT.findall(text):
        if re.fullmatch(r"[0-9a-f]+", token, re.IGNORECASE):
            continue
        if _entropy(token) >= 4.2:
            return True
    return False


def _term_matches(text: str, term: str) -> bool:
    escaped = re.escape(term)
    if term[0].isalnum() and term[-1].isalnum():
        return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None
    return term in text


def _checked_files() -> Iterator[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    for relative in completed.stdout.splitlines():
        path = ROOT / relative
        if path.is_file() and not path.is_symlink():
            yield path


def _check_source(terms: tuple[str, ...]) -> None:
    for path in _checked_files():
        if _contains_prohibited(path.read_bytes(), terms):
            raise GateFailure


def _git_blobs() -> Iterator[bytes]:
    completed = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    seen: set[str] = set()
    for line in completed.stdout.splitlines():
        object_id = line.partition(" ")[0]
        if object_id in seen:
            continue
        seen.add(object_id)
        object_type = subprocess.run(
            ["git", "cat-file", "-t", object_id], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        ).stdout.strip()
        if object_type == "blob":
            yield subprocess.run(
                ["git", "cat-file", "blob", object_id], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            ).stdout


def _check_git_objects(terms: tuple[str, ...]) -> None:
    if any(_contains_prohibited(blob, terms) for blob in _git_blobs()):
        raise GateFailure


def _safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise GateFailure


def _check_wheel(path: Path, terms: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path) as archive:
        records: dict[str, tuple[str, str]] = {}
        members = [member for member in archive.infolist() if not member.is_dir()]
        for member in members:
            _safe_member(member.filename)
            if member.external_attr >> 16 & 0o170000 == 0o120000:
                raise GateFailure
            if _contains_prohibited(member.filename.encode(), terms):
                raise GateFailure
            if member.filename.endswith(".dist-info/RECORD"):
                for row in csv.reader(archive.read(member).decode("utf-8").splitlines()):
                    if len(row) != 3:
                        raise GateFailure
                    records[row[0]] = (row[1], row[2])
            elif _contains_prohibited(archive.read(member), terms):
                raise GateFailure
        if not records or set(records) != {member.filename for member in members}:
            raise GateFailure
        for member in members:
            digest, size = records[member.filename]
            data = archive.read(member)
            if member.filename.endswith(".dist-info/RECORD"):
                if digest or size:
                    raise GateFailure
                continue
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
            if digest != f"sha256={expected}" or size != str(len(data)):
                raise GateFailure


def _check_sdist(path: Path, terms: tuple[str, ...]) -> None:
    with tarfile.open(path) as archive:
        roots: set[str] = set()
        for member in archive.getmembers():
            _safe_member(member.name)
            roots.add(PurePosixPath(member.name).parts[0])
            if member.issym() or member.islnk():
                raise GateFailure
            if _contains_prohibited(member.name.encode(), terms):
                raise GateFailure
            if member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None or _contains_prohibited(extracted.read(), terms):
                    raise GateFailure
        if len(roots) != 1:
            raise GateFailure


def _receipt(label: str, action: Callable[[], None]) -> None:
    action()
    print(f"{label}: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--denylist", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--sdist", required=True, type=Path)
    args = parser.parse_args()
    try:
        terms = _denylist(args.denylist)
        _receipt("denylist", lambda: None)
        _receipt("source", lambda: _check_source(terms))
        _receipt("git-objects", lambda: _check_git_objects(terms))
        _receipt("wheel", lambda: _check_wheel(args.wheel, terms))
        _receipt("sdist", lambda: _check_sdist(args.sdist, terms))
    except (GateFailure, OSError, subprocess.SubprocessError, tarfile.TarError, zipfile.BadZipFile, UnicodeError):
        print("privacy-gate: FAIL")
        return 1
    print("privacy-gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
