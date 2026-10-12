"""update-conda-forge-pinning: distributions on the shared pinning move together."""

import maintenance
import robostack as rs


def _setup(monkeypatch, own):
    monkeypatch.setattr(rs, "distros", lambda: ["humble", "jazzy", "rolling"])
    monkeypatch.setattr(rs, "settings", lambda d: {"conda_forge_pinning_version": "1"} if d in own else {})
    calls = []
    monkeypatch.setattr(maintenance, "update_shared_pinning",
                        lambda: calls.append("shared") or maintenance.Result("shared", "s"))
    return calls


def test_a_distribution_on_the_shared_pinning_updates_all_of_them(monkeypatch):
    calls = _setup(monkeypatch, own=set())
    assert maintenance.uses_shared_pinning("jazzy")
    assert maintenance.update_pinning("jazzy").title == "shared"
    assert calls == ["shared"]


def test_repository_wide_update_runs_the_shared_one_once(monkeypatch, tmp_path):
    calls = _setup(monkeypatch, own={"rolling"})
    monkeypatch.setattr(maintenance, "update_pinning",
                        lambda d: calls.append(d) or maintenance.Result(d, d))
    assert maintenance.main("update-pinning", ["--summary", str(tmp_path / "s.md")]) == 0
    assert calls == ["shared", "rolling"]


def test_no_shared_update_when_every_distribution_has_its_own(monkeypatch, tmp_path):
    calls = _setup(monkeypatch, own={"humble", "jazzy", "rolling"})
    monkeypatch.setattr(maintenance, "update_pinning",
                        lambda d: calls.append(d) or maintenance.Result(d, d))
    maintenance.main("update-pinning", ["--summary", str(tmp_path / "s.md")])
    assert calls == ["humble", "jazzy", "rolling"]
