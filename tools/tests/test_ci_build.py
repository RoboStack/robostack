"""The PR build must stop its grandchildren before publishing a reusable cache."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX CI supervisor")


def command(cache, timeout, script):
    return [sys.executable, str(ROOT / "tools/ci_build.py"), "--cache-dir", str(cache),
            "--timeout", str(timeout), "--", sys.executable, str(script)]


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, None])
def test_interruption_stops_descendants_and_preserves_only_finished_archives(tmp_path, signum):
    cache = tmp_path / "packages"
    cache.mkdir()
    (cache / "restored.conda").write_text("cached")
    script = tmp_path / "build.py"
    # A descendant that ignores graceful termination and keeps modifying the output.
    script.write_text('''import os, signal, subprocess, sys, time
from pathlib import Path
cache = Path(sys.argv[0]).parent / "packages"
(cache / "completed.conda").write_text("complete")
print(f"Archive written to '{cache / 'completed.conda'}'", flush=True)
for i in range(3):
    (cache / f"partial-{i}.conda").write_text("incomplete")
child = subprocess.Popen([sys.executable, "-c", """
import signal, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGINT, signal.SIG_IGN)
while True:
    Path(sys.argv[1]).write_text(str(time.monotonic_ns()))
    time.sleep(.01)
""", str(cache / "heartbeat")])
(cache / "ready").write_text(str(os.getpid()))
child.wait()
''')
    output = tmp_path / "github-output"
    env = {**os.environ, "GITHUB_OUTPUT": str(output)}
    proc = subprocess.Popen(command(cache, 2 if signum is None else 30, script), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    group = None
    try:
        deadline = time.monotonic() + 10
        while not ((cache / "heartbeat").exists() and (cache / "ready").exists()):
            assert proc.poll() is None, proc.communicate()[0].decode()
            assert time.monotonic() < deadline, "fake build did not start"
            time.sleep(.01)
        group = int((cache / "ready").read_text())
        if signum is not None:
            proc.send_signal(signum)
        stdout, _ = proc.communicate(timeout=10)
        assert proc.returncode == (124 if signum is None else 128 + signum), stdout.decode()
        assert {p.name for p in cache.glob("*.conda")} == {"restored.conda", "completed.conda"}
        assert output.read_text() == "cache-ready=true\n"
        heartbeat = (cache / "heartbeat").read_bytes()
        time.sleep(.1)
        assert (cache / "heartbeat").read_bytes() == heartbeat
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if group is not None:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize("status", [0, 7])
def test_exit_status_and_replaced_incomplete_archive(tmp_path, status):
    (tmp_path / "replaced.conda").write_text("previous build")
    script = tmp_path / "build.py"
    script.write_text(f'''from pathlib import Path
import sys
p = Path(__file__).parent / "replaced.conda"
p.write_text("partial")
sys.exit({status})
''')
    result = subprocess.run(command(tmp_path, 10, script), capture_output=True, timeout=15,
                            env={**os.environ, "GITHUB_OUTPUT": str(tmp_path / "outputs")})
    assert result.returncode == status, result.stdout.decode()
    assert not (tmp_path / "replaced.conda").exists()


def test_workflow_only_saves_stopped_builds_and_verifies_cache_before_deleting():
    workflow = yaml.safe_load((ROOT / ".github/workflows/testpr.yaml").read_text())
    steps = workflow["jobs"]["build"]["steps"]
    build = next(s for s in steps if s.get("id") == "build-recipes")
    save = next(s for s in steps if s.get("id") == "save-cache")
    prune = next(s for s in steps if s.get("name") == "Drop this pull request's superseded build caches")
    assert build["timeout-minutes"] < 360
    assert "tools/ci_build.py" in build["run"]
    assert "steps.build-recipes.outputs.cache-ready == 'true'" in save["if"]
    assert "github.event.pull_request.head.repo.full_name == github.repository" in prune["if"]
    assert '--ref "$GITHUB_REF"' in prune["run"]
    assert "if ! ids=" in prune["run"]
    assert prune["run"].index("exit 0") < prune["run"].index("cache delete")


@pytest.mark.parametrize("lookup_status,ids,deleted", [(0, "11\n22", "11\n22\n"),
                                                       (1, "11", ""), (0, "", "")])
def test_cache_pruning_requires_verified_replacement(tmp_path, lookup_status, ids, deleted):
    workflow = yaml.safe_load((ROOT / ".github/workflows/testpr.yaml").read_text())
    prune = next(s for s in workflow["jobs"]["build"]["steps"]
                 if s.get("name") == "Drop this pull request's superseded build caches")
    pixi = tmp_path / "pixi"
    pixi.write_text('''#!/bin/bash
if [ "$4" = list ]; then
  printf '%s\\n' "$IDS"
  exit "$LOOKUP_STATUS"
fi
[ "$4" = delete ] || exit 99
printf '%s\\n' "$5" >> "$DELETED"
''')
    pixi.chmod(0o755)
    record = tmp_path / "deleted"
    result = subprocess.run(["bash", "-c", prune["run"]], capture_output=True, text=True, timeout=10,
                            env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
                                 "IDS": ids, "LOOKUP_STATUS": str(lookup_status), "DELETED": str(record),
                                 "GITHUB_REPOSITORY": "RoboStack/robostack", "GITHUB_REF": "refs/pull/144/merge",
                                 "PREFIX": "cache-", "KEEP": "cache-new"})
    assert result.returncode == 0, result.stderr
    assert (record.read_text() if record.exists() else "") == deleted
