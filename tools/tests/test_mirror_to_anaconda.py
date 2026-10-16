"""mirror_to_anaconda: which packages are uploaded, and the download check."""

import hashlib
from pathlib import Path

import pytest

import mirror_to_anaconda as mirror


def test_only_packages_missing_on_anaconda_are_uploaded() -> None:
    source = {"a-1-0.conda": {}, "b-1-0.conda": {}, "c-1-0.tar.bz2": {}}
    destination = {"b-1-0.conda": {}}
    assert mirror.missing_packages(source, destination) == ["a-1-0.conda", "c-1-0.tar.bz2"]


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


def test_download_rejects_a_sha256_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = mirror.session
    monkeypatch.setattr(session, "get", lambda url: FakeResponse(b"package"))
    target = tmp_path / "a-1-0.conda"

    mirror.download("url", hashlib.sha256(b"package").hexdigest(), target)
    assert target.read_bytes() == b"package"

    with pytest.raises(RuntimeError, match="sha256 mismatch"):
        mirror.download("url", hashlib.sha256(b"other").hexdigest(), tmp_path / "b.conda")
