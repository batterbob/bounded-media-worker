import base64
import hashlib
import importlib.util
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

_GATE_PATH = Path(__file__).parents[1] / "tools" / "privacy_gate.py"
_GATE_SPEC = importlib.util.spec_from_file_location("privacy_gate", _GATE_PATH)
assert _GATE_SPEC is not None and _GATE_SPEC.loader is not None
gate = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(gate)


def _init_repository(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _add_tracked_file(repository: Path, name: str, content: bytes) -> None:
    target = repository / name
    target.write_bytes(content)
    subprocess.run(["git", "add", "--", name], cwd=repository, check=True)


def _write_wheel(path: Path, member_name: str, content: bytes) -> None:
    record_name = "bounded_media_worker-0.1.dist-info/RECORD"
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii")
    record = f"{member_name},sha256={digest},{len(content)}\n{record_name},,\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member_name, content)
        archive.writestr(record_name, record)


def _write_sdist(path: Path, member_name: str, content: bytes) -> None:
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))


@pytest.mark.parametrize("entry", ["a", "---", "***", "!!!", "invalid\x00entry"])
def test_denylist_rejects_malformed_active_entry(tmp_path: Path, entry: str) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(f"# comment\n\n{entry}\nvalid term\n", encoding="utf-8")

    with pytest.raises(gate.GateFailure):
        gate._denylist(denylist)


def test_denylist_allows_blank_lines_and_comments(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text("\n  # comment\nvalid term\n", encoding="utf-8")

    assert gate._denylist(denylist) == ("valid term",)


@pytest.mark.parametrize(
    ("name", "content", "term"),
    [
        ("restricted-name.txt", b"safe content", "restricted"),
        ("ordinary.txt", b"contains restricted content", "restricted"),
    ],
)
def test_source_scans_tracked_filenames_and_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, content: bytes, term: str
) -> None:
    repository = tmp_path / "repository"
    _init_repository(repository)
    _add_tracked_file(repository, name, content)
    monkeypatch.setattr(gate, "ROOT", repository)

    with pytest.raises(gate.GateFailure):
        gate._check_source((term,))


def test_git_blob_scan_includes_unreachable_objects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repository"
    _init_repository(repository)
    payload = b"unreachable blob payload"
    subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repository,
        check=True,
        input=payload,
        stdout=subprocess.PIPE,
    )
    monkeypatch.setattr(gate, "ROOT", repository)

    assert payload in tuple(gate._git_blobs())


@pytest.mark.parametrize(
    ("writer", "archive_name", "member_name", "content"),
    [
        (_write_wheel, "package.whl", "package/restricted-name.py", b"safe content"),
        (_write_wheel, "package.whl", "package/module.py", b"restricted content"),
        (_write_sdist, "package.tar.gz", "package/restricted-name.py", b"safe content"),
        (_write_sdist, "package.tar.gz", "package/module.py", b"restricted content"),
    ],
)
def test_archives_scan_member_names_and_contents(
    tmp_path: Path,
    writer: object,
    archive_name: str,
    member_name: str,
    content: bytes,
) -> None:
    archive = tmp_path / archive_name
    writer(archive, member_name, content)  # type: ignore[operator]

    with pytest.raises(gate.GateFailure):
        if archive.suffix == ".whl":
            gate._check_wheel(archive, ("restricted",))
        else:
            gate._check_sdist(archive, ("restricted",))


def test_receipts_do_not_disclose_arguments_or_denylist_terms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    denylist = tmp_path / "private-denylist.txt"
    denylist.write_text("confidential-term\n", encoding="utf-8")
    monkeypatch.setattr(gate, "_check_source", lambda terms: None)
    monkeypatch.setattr(gate, "_check_git_objects", lambda terms: None)
    monkeypatch.setattr(gate, "_check_wheel", lambda path, terms: None)
    monkeypatch.setattr(gate, "_check_sdist", lambda path, terms: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "privacy_gate.py",
            "--denylist",
            str(denylist),
            "--wheel",
            str(tmp_path / "confidential-wheel.whl"),
            "--sdist",
            str(tmp_path / "confidential-source.tar.gz"),
        ],
    )

    assert gate.main() == 0
    output = capsys.readouterr().out
    assert output == "denylist: PASS\nsource: PASS\ngit-objects: PASS\nwheel: PASS\nsdist: PASS\nprivacy-gate: PASS\n"
    assert "confidential" not in output
    assert str(tmp_path) not in output
