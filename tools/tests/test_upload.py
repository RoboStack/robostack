"""rs <distro> upload: robostack-<distro> on anaconda.org, then on prefix.dev."""

import pytest

import robostack as rs


@pytest.fixture
def calls(monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(rs, "run", lambda cmd, cwd: made.append(cmd) or 0)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
    monkeypatch.delenv("ROBOSTACK_UPLOAD_CHANNEL", raising=False)
    monkeypatch.delenv("ANACONDA_API_KEY", raising=False)
    return made


def test_uploads_to_anaconda_then_prefix(calls, monkeypatch, tmp_path):
    monkeypatch.setenv("ANACONDA_API_TOKEN", "secret")

    assert rs.upload("humble", ["a.conda"], tmp_path) == 0
    assert calls == [
        ["rattler-build", "upload", "anaconda", "-o", "robostack-humble", "--force", "a.conda"],
        ["rattler-build", "upload", "prefix", "-c", "robostack-humble", "--skip-existing",
         "--generate-attestation", "a.conda"],
    ]
    # the token is passed in the environment, not on the command line
    assert rs.os.environ["ANACONDA_API_KEY"] == "secret"


def test_no_prefix_upload_when_anaconda_fails(calls, monkeypatch, tmp_path):
    monkeypatch.setenv("ANACONDA_API_TOKEN", "secret")
    monkeypatch.setattr(rs, "run", lambda cmd, cwd: calls.append(cmd) or 1)

    assert rs.upload("jazzy", ["a.conda"], tmp_path) == 1
    # three attempts, all on anaconda.org: prefix.dev must not get a package anaconda.org lacks
    assert [c[2] for c in calls] == ["anaconda"] * 3


def test_fails_without_the_anaconda_token(calls, monkeypatch, tmp_path):
    monkeypatch.delenv("ANACONDA_API_TOKEN", raising=False)

    assert rs.upload("jazzy", ["a.conda"], tmp_path) == 1
    assert calls == []


def test_upload_channel_override_only_uploads_there(calls, monkeypatch, tmp_path):
    monkeypatch.setenv("ROBOSTACK_UPLOAD_CHANNEL", "someone/test")
    monkeypatch.delenv("ANACONDA_API_TOKEN", raising=False)

    assert rs.upload("lyrical", ["a.conda"], tmp_path) == 0
    assert calls == [["rattler-build", "upload", "prefix", "-c", "someone/test", "--skip-existing",
                      "--generate-attestation", "a.conda"]]


def test_upload_channel_none_skips_uploading(calls, monkeypatch, tmp_path):
    monkeypatch.setenv("ROBOSTACK_UPLOAD_CHANNEL", "none")

    assert rs.upload("rolling", ["a.conda"], tmp_path) == 0
    assert calls == []


def test_every_distribution_reads_its_prefix_channel():
    assert rs.channel_url("humble") == "https://prefix.dev/robostack-humble"
