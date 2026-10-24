"""Measured build times, for packing the build jobs by time (vinca-gha --timings).

Each build-branch job records how long each of its recipes took to build (`rs <distro>
build-ci`) and to upload (`rs <distro> upload`), in distros/<distro>/work/build_timings.jsonl,
and keeps that file as an artifact (vinca-gha --keep-file). `robostack-bot
update-build-timings` merges the last week's into shared/build_timings/<platform>.json,
{recipe: {distro: seconds}}, one recipe per line, and `rs <distro> gha` hands vinca-gha
each recipe's average over the distributions: a recipe new to one distribution still has a
time (the names are the same, ros2-<package>). The compatibility recipes
(ros-<distro>-<name>) aren't kept: they get ALIAS_SECONDS, and their uploads count for
ros2-<name>, which they are built right after.

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
# a compatibility recipe (ros-<distro>-<name>) only repackages: measured median, the same
# everywhere, so the files don't keep one per distribution
ALIAS_SECONDS = 0.3


def note(distro: str, recipe: str, seconds: float, upload: bool = False) -> None:
    """Record a recipe's build (or upload) time in the work directory's journal."""
    from vinca.platforms import get_conda_subdir

    entry = {"platform": get_conda_subdir(), "recipe": recipe, "seconds": round(seconds, 1)}
    if upload:
        entry["upload"] = True
    with (rs.work_dir(distro) / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def collect(days: int = 8) -> int:
    """Merge the build times the build-branch runs of the last `days` days recorded into
    shared/build_timings/ (newer runs win), uploads added to the build that precedes them in
    the job's journal; returns how many build times were recorded."""
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
                    recipe, alias = entry["recipe"], f"ros-{distro}-"
                    by_distro = files.setdefault(entry["platform"], {})
                    if entry.get("upload"):
                        times = by_distro.get(recipe.replace(alias, "ros2-", 1), {})
                        if distro in times:
                            times[distro] = round(times[distro] + entry["seconds"], 1)
                        continue
                    if recipe.startswith(alias):
                        continue  # a compatibility recipe: ALIAS_SECONDS
                    by_distro.setdefault(recipe, {})[distro] = entry["seconds"]
                    count += 1
    TIMINGS.mkdir(parents=True, exist_ok=True)
    for platform, recipes in files.items():
        (TIMINGS / f"{platform}.json").write_text(dumps(recipes))
    return count


def dumps(recipes: dict) -> str:
    """One recipe per line, sorted: small files, and a changed time is a one-line diff."""
    lines = [f"{json.dumps(r)}: {json.dumps(recipes[r], sort_keys=True)}" for r in sorted(recipes)]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def vinca_timings(distro: str, platform: str, path: Path) -> bool:
    """Write vinca-gha's --timings file for the platform: each recipe's average over the
    distributions, and ALIAS_SECONDS for the distribution's compatibility recipes
    (ros-<distro>-<name>, built right after ros2-<name>). False when there are no times yet."""
    source = TIMINGS / f"{platform}.json"
    if not source.is_file():
        return False
    recipes = {r: round(statistics.fmean(by.values()), 1) for r, by in json.loads(source.read_text()).items()}
    # unmeasured recipes: the median of the packages (ros2-*)
    default = statistics.median([s for r, s in recipes.items() if r.startswith("ros2-")] or list(recipes.values()))
    recipes.update({f"ros-{distro}-{r[len('ros2-'):]}": ALIAS_SECONDS for r in list(recipes) if r.startswith("ros2-")})
    path.write_text(json.dumps({"recipes": recipes, "default": default}) + "\n")
    return True


if __name__ == "__main__":
    print(f"{collect()} build times recorded")
