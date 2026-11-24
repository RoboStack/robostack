"""rs <distro> gha: the build workflow from .github/build-template.yaml (vinca-rs workflow)."""

import build_timings
import robostack as rs


def gha(monkeypatch, tmp_path, distro, platform):
    """Run generate_gha with vinca-rs stubbed out; return the vinca-rs command."""
    calls = []
    work, root = tmp_path / "work", tmp_path / "root"
    work.mkdir(exist_ok=True)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    def fake_run(cmd, cwd):
        calls.append(cmd)
        out = cmd[cmd.index("--out") + 1]
        open(out, "w").write("name: build\n")
        return 0

    monkeypatch.setattr(rs, "run", fake_run)
    monkeypatch.setattr(rs, "work_dir", lambda distro: work)
    monkeypatch.setattr(rs, "ROOT", root)
    assert rs.generate_gha(distro, ["--platform", platform]) == 0
    return calls[-1], work, root


def variables(cmd):
    return dict(cmd[i + 1].split("=", 1) for i, a in enumerate(cmd) if a == "--var")


def test_gha_renders_the_template_for_the_distribution(monkeypatch, tmp_path):
    monkeypatch.setattr(build_timings, "TIMINGS", tmp_path / "no-timings")
    cmd, _, root = gha(monkeypatch, tmp_path, "lyrical", "linux-64")
    assert cmd[:2] == [rs.VINCA_RS, "workflow"]
    assert cmd[cmd.index("--template") + 1] == str(root / ".github" / "build-template.yaml")
    assert cmd[cmd.index("--out") + 1] == str(root / ".github" / "workflows" / "build.yaml")
    assert variables(cmd) == {
        "distro": "lyrical",
        "branch": "buildbranch_lyrical_linux_64",
        # each distribution has its own anaconda.org token
        "secret": "ANACONDA_API_TOKEN_LYRICAL",
        "keep_file": f"distros/lyrical/work/{build_timings.JOURNAL}",
    }


def test_gha_uses_the_measured_times(monkeypatch, tmp_path):
    monkeypatch.setattr(build_timings, "TIMINGS", tmp_path / "timings")
    cmd, _, _ = gha(monkeypatch, tmp_path, "jazzy", "linux-64")
    assert "--timings" not in cmd  # no times yet
    (tmp_path / "timings").mkdir()
    (tmp_path / "timings" / "linux-64.json").write_text('{"ros2-a": {"jazzy": 3.0}}\n')
    cmd, work, _ = gha(monkeypatch, tmp_path, "jazzy", "linux-64")
    assert cmd[cmd.index("--timings") + 1] == "build_timings.json"
    assert (work / "build_timings.json").is_file()
