"""Measured build times, for packing the build jobs by time (vinca-gha --timings).

Each build-branch job records how long each of its recipes took to build (`rs <distro>
build-ci`, in distros/<distro>/work/build_timings.jsonl) and keeps that file as an artifact
(vinca-gha --keep-file). `robostack-bot update-build-timings` merges the last week's into
shared/build_timings/<platform>.json, {recipe: {distro: seconds}}, and `rs <distro> gha`
hands vinca-gha each recipe's average over the distributions: a recipe new to one
distribution still has a time (the names are the same, ros2-<package>).

    pixi run python tools/build_timings.py   # what the bot command does
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robostack as rs

TIMINGS = rs.ROOT / "shared" / "build_timings"
JOURNAL = "build_timings.jsonl"


def note(distro: str, recipe: str, seconds: float) -> None:
    """Record a recipe's build time in the work directory's journal."""
    from vinca.platforms import get_conda_subdir

    entry = {"platform": get_conda_subdir(), "recipe": recipe, "seconds": round(seconds, 1)}
    with (rs.work_dir(distro) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def collect(days: int = 8) -> int:
    """Merge the build times the build-branch runs of the last `days` days recorded into
    shared/build_timings/ (newer runs win); returns how many times were recorded."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    runs = json.loads(subprocess.run(
        ["gh", "run", "list", "--repo", "RoboStack/robostack", "--workflow", "build.yaml", "--status", "completed",
         "--created", f">={since}", "--limit", "1000", "--json", "databaseId,headBranch,createdAt"],
        capture_output=True, text=True, check=True).stdout)
    files = {p.stem: json.loads(p.read_text()) for p in TIMINGS.glob("*.json")}
    count = 0
    with tempfile.TemporaryDirectory() as tmp:
        for run in sorted(runs, key=lambda r: r["createdAt"]):
            distro = run["headBranch"].removeprefix("buildbranch_").split("_")[0]
            out = Path(tmp) / str(run["databaseId"])
            subprocess.run(["gh", "run", "download", str(run["databaseId"]), "--repo", "RoboStack/robostack",
                            "--dir", str(out)], capture_output=True, check=False)
            for journal in sorted(out.rglob(JOURNAL)):
                for line in journal.read_text().splitlines():
                    entry = json.loads(line)
                    files.setdefault(entry["platform"], {}).setdefault(entry["recipe"], {})[distro] = entry["seconds"]
                    count += 1
    TIMINGS.mkdir(parents=True, exist_ok=True)
    for platform, recipes in files.items():
        (TIMINGS / f"{platform}.json").write_text(json.dumps(recipes, indent=0, sort_keys=True) + "\n")
    return count


def vinca_timings(platform: str, path: Path) -> bool:
    """Write vinca-gha's --timings file for the platform: each recipe's average over the
    distributions. False when there are no times yet."""
    source = TIMINGS / f"{platform}.json"
    if not source.is_file():
        return False
    recipes = {r: round(statistics.fmean(by.values()), 1) for r, by in json.loads(source.read_text()).items()}
    path.write_text(json.dumps({"recipes": recipes}) + "\n")
    return True


if __name__ == "__main__":
    print(f"{collect()} build times recorded")
