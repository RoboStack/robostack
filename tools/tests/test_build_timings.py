import json
import subprocess
from pathlib import Path

import build_timings


def test_note_records_build_times(tmp_path, monkeypatch):
    monkeypatch.setattr(build_timings.rs, "work_dir", lambda distro: tmp_path)
    build_timings.note("jazzy", "ros2-a", 12.34)
    build_timings.note("jazzy", "ros-jazzy-a", 1.0)
    entries = [json.loads(line) for line in (tmp_path / build_timings.JOURNAL).read_text().splitlines()]
    assert [(e["recipe"], e["seconds"]) for e in entries] == [("ros2-a", 12.3), ("ros-jazzy-a", 1.0)]
    assert all(e["platform"] for e in entries)


def test_collect_merges_the_runs_journals(tmp_path, monkeypatch):
    monkeypatch.setattr(build_timings, "TIMINGS", tmp_path / "timings")
    runs = [{"databaseId": 2, "headBranch": "buildbranch_jazzy_linux_64", "createdAt": "2026-10-22T02:00:00Z"},
            {"databaseId": 1, "headBranch": "buildbranch_jazzy_linux_64", "createdAt": "2026-10-22T01:00:00Z"},
            {"databaseId": 3, "headBranch": "buildbranch_lyrical_linux_64", "createdAt": "2026-10-22T03:00:00Z"}]
    journals = {1: [("ros2-a", 10.0), ("ros2-b", 5.0)], 2: [("ros2-a", 12.0)], 3: [("ros2-a", 20.0)]}

    def run(cmd, **kwargs):
        if cmd[1:3] == ["run", "list"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps(runs), "")
        run_id = int(cmd[3])
        job = Path(cmd[cmd.index("--dir") + 1]) / "stage_0_job_0-1"
        job.mkdir(parents=True)
        (job / build_timings.JOURNAL).write_text("".join(
            json.dumps({"platform": "linux-64", "recipe": r, "seconds": s}) + "\n" for r, s in journals[run_id]))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(build_timings.subprocess, "run", run)
    assert build_timings.collect() == 4
    # the newer jazzy run wins; each distribution keeps its own time
    assert json.loads((tmp_path / "timings" / "linux-64.json").read_text()) == {
        "ros2-a": {"jazzy": 12.0, "lyrical": 20.0}, "ros2-b": {"jazzy": 5.0}}
    # vinca-gha gets the average over the distributions
    out = tmp_path / "vinca.json"
    assert build_timings.vinca_timings("linux-64", out)
    assert json.loads(out.read_text()) == {"recipes": {"ros2-a": 16.0, "ros2-b": 5.0}, "default": 10.5}
    assert not build_timings.vinca_timings("win-64", out)


def test_update_build_timings_command(tmp_path, monkeypatch):
    import maintenance

    assert maintenance.parse_command("@robostack-bot update-build-timings", "MEMBER") == [
        {"command": "update-build-timings", "distro": "", "args": "", "preview": False}]
    assert maintenance.parse_command("@robostack-bot update-build-timings", "NONE") == []
    monkeypatch.setattr(build_timings, "TIMINGS", tmp_path)

    def collect():
        (tmp_path / "linux-64.json").write_text('{"ros2-a": {"jazzy": 1.0}}\n')
        return 1

    monkeypatch.setattr(build_timings, "collect", collect)
    result = maintenance.update_build_timings()
    assert result.changed and "linux-64.json" in result.summary
    assert not maintenance.update_build_timings().changed  # nothing new: no PR


def test_gha_keeps_the_journal_and_uses_the_times(tmp_path, monkeypatch):
    import robostack as rs

    work, root = tmp_path / "work", tmp_path / "root"
    work.mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    calls = []

    def fake_run_tee(cmd, cwd):
        calls.append(cmd)
        (work / "linux.yml").write_text("name: build\njobs:\n  stage_0_job_0:\n    steps: []\n")
        return 0, b""

    monkeypatch.setattr(rs, "run_tee", fake_run_tee)
    monkeypatch.setattr(rs, "work_dir", lambda distro: work)
    monkeypatch.setattr(rs, "ROOT", root)
    monkeypatch.setattr(build_timings, "TIMINGS", tmp_path / "timings")
    assert rs.generate_gha("jazzy", ["--platform", "linux-64"]) == 0
    assert "--keep-file" in calls[-1] and "--timings" not in calls[-1]  # no times yet
    (tmp_path / "timings").mkdir()
    (tmp_path / "timings" / "linux-64.json").write_text('{"ros2-a": {"jazzy": 3.0}}\n')
    assert rs.generate_gha("jazzy", ["--platform", "linux-64"]) == 0
    assert calls[-1][calls[-1].index("--timings") + 1] == "build_timings.json"
    assert json.loads((work / "build_timings.json").read_text()) == {"recipes": {"ros2-a": 3.0}, "default": 3.0}
