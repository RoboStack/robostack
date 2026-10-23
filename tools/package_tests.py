"""Run the tests bundled in the published packages again, against today's dependencies.

Packages carry their recipe tests (rattler-build bundles them in info/tests), so they
can be tested again after they were uploaded. Installing each one with the newest
dependencies from conda-forge catches breakages that come from conda-forge rather
than from RoboStack, e.g. an ABI change in a dependency that a RoboStack package was
built against (RoboStack/ros-humble#274). The nightly package-tests workflow runs this
for every distribution and platform and keeps one issue per distribution
("<distro>: package tests", label package-tests), closed when every test passes.

    python tools/package_tests.py select --distro jazzy --platform linux-64
    python tools/package_tests.py run --distro jazzy --platform linux-64 --results results/jazzy-linux-64.json
    python tools/package_tests.py report results/   # in GitHub Actions also updates the issues

The tested packages are the ones with a test file (shared/tests/<package>.yaml or
distros/<distro>/tests/<package>.yaml): vinca adds no tests of its own. Each is tested in
its newest build on the distribution's channel, every variant of it (e.g. each Python).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robostack as rs

REPORT_LABEL = "package-tests"
REPORT_MARKER = "<!-- robostack-package-tests -->"
MAX_ISSUE_BODY = 60000  # GitHub's limit is 65536 characters
LOG_TAIL = 60  # lines of a failed test's output kept in the results
# a test that rattler-build ran: a script test prints "Testing commands:", the others
# "✔ <kind> test passed!" (not its closing "all tests passed!", which it also prints
# for a package without tests)
RAN_TEST = re.compile(r"^Testing commands:|\b(?<!all )tests? passed!")


def tested_packages(distro: str) -> list[str]:
    """Package names with a test file, shared or the distribution's own."""
    names = set()
    for tests in (rs.ROOT / "shared" / "tests", rs.DISTROS / distro / "tests"):
        names.update(p.stem for p in tests.glob("*.yaml"))
    return sorted(names)


def fetch_json(url: str, attempts: int = 3) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return {}
            if attempt == attempts:
                raise
        except OSError:
            if attempt == attempts:
                raise
        time.sleep(10 * attempt)
    return {}


def newest_builds(repodata: dict, names: list[str]) -> list[dict]:
    """For each name, every variant of its newest build: the records with the version
    and build number of the newest upload (one per build string, e.g. per Python)."""
    records: dict[str, list[dict]] = {}
    for section in ("packages", "packages.conda"):
        for filename, record in (repodata.get(section) or {}).items():
            if record.get("name") in names:
                records.setdefault(record["name"], []).append({**record, "fn": filename})
    selected = []
    for name in sorted(records):
        newest = max(records[name], key=lambda r: (r.get("build_number", 0), r.get("timestamp", 0)))
        variants: dict[str, dict] = {}
        for record in records[name]:
            if (record["version"], record.get("build_number")) != (newest["version"], newest.get("build_number")):
                continue
            # the same build in both formats: prefer .conda
            if record["build"] not in variants or record["fn"].endswith(".conda"):
                variants[record["build"]] = record
        selected += sorted(variants.values(), key=lambda r: r["build"])
    return selected


def select(distro: str, platform: str) -> list[dict]:
    """The package files to test on this platform: {name, version, build, subdir, url}."""
    names = tested_packages(distro)
    base = rs.repodata_url(distro)
    selected = []
    for subdir in (platform, "noarch"):
        repodata = fetch_json(f"{base}/{subdir}/repodata.json")
        for record in newest_builds(repodata, names):
            selected.append({"name": record["name"], "version": record["version"], "build": record["build"],
                             "subdir": subdir, "url": f"{base}/{subdir}/{record['fn']}"})
    return selected


def test_command(distro: str, package_file: Path) -> list[str]:
    """rattler-build test with the build channels: the distribution's channel for the
    other RoboStack packages, conda-forge for the rest (newest versions, not a lock)."""
    return ["rattler-build", "test", "--package-file", str(package_file), "-c", rs.channel_url(distro),
            "-c", rs.CONDA_FORGE, "--channel-priority", "disabled", "--log-style", "plain"]


def test_package(distro: str, package_file: Path) -> tuple[bool, str, int]:
    """Run the package's bundled tests: (passed, output, number of tests that ran)."""
    proc = subprocess.run(test_command(distro, package_file), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    log = proc.stdout + proc.stderr
    return proc.returncode == 0, log, sum(bool(RAN_TEST.search(line.strip())) for line in log.splitlines())


def tail(text: str, lines: int) -> str:
    return "\n".join(text.splitlines()[-lines:])


def run(distro: str, platform: str, results: Path, only: list[str] | None = None) -> int:
    """Test the selected packages (only these names, if given) one by one; write the
    results (JSON) and return 1 when one failed."""
    packages = [p for p in select(distro, platform) if not only or p["name"] in only]
    print(f"{distro} {platform}: {len(packages)} package files to test", flush=True)
    outcome = []
    with tempfile.TemporaryDirectory() as tmp:
        for package in packages:
            label = f"{package['name']} {package['version']} {package['build']}"
            print(f"::group::{label}" if os.environ.get("GITHUB_ACTIONS") else f"== {label}", flush=True)
            package_file = Path(tmp) / package["url"].rsplit("/", 1)[1]
            started = time.monotonic()
            try:
                urllib.request.urlretrieve(package["url"], package_file)
                ok, log, count = test_package(distro, package_file)
                # launch tests can time out on DDS discovery: a failure is tried once more,
                # and a pass then is reported as flaky
                flaky = False
                if not ok:
                    print(log, "\n❌ failed, trying again", flush=True)
                    ok, log, count = test_package(distro, package_file)
                    flaky = ok
            except OSError as error:
                ok, log, count, flaky = False, f"download failed: {error}", 0, False
            finally:
                package_file.unlink(missing_ok=True)
            print(log, flush=True)
            if os.environ.get("GITHUB_ACTIONS"):
                print("::endgroup::", flush=True)
            # a build from before its test file was added carries no tests: not a pass
            status = "failed" if not ok else "flaky" if flaky else "passed" if count else "no-tests"
            print(f"{ {'passed': '✅', 'flaky': '⚠️', 'failed': '❌', 'no-tests': '➖'}[status]} {label}: {status} "
                  f"({count} tests, {time.monotonic() - started:.0f} s)", flush=True)
            outcome.append({**package, "ok": ok, "status": status, "tests": count,
                            **({} if ok else {"log": tail(log, LOG_TAIL)})})
    results.parent.mkdir(parents=True, exist_ok=True)
    results.write_text(json.dumps({"distro": distro, "platform": platform, "packages": outcome}, indent=1))
    failed = [p for p in outcome if not p["ok"]]
    untested = [p for p in outcome if p["status"] == "no-tests"]
    flaky = [p for p in outcome if p["status"] == "flaky"]
    print(f"{distro} {platform}: {len(outcome) - len(failed) - len(untested)} passed ({len(flaky)} on the second "
          f"try), {len(failed)} failed, {len(untested)} without bundled tests", flush=True)
    return 1 if failed else 0


def load_results(directory: Path) -> dict[str, list[dict]]:
    """distro -> results of each platform (from run's JSON files, searched recursively:
    GitHub Actions downloads every artifact into its own directory)."""
    by_distro: dict[str, list[dict]] = {}
    for path in sorted(directory.rglob("*.json")):
        data = json.loads(path.read_text())
        by_distro.setdefault(data["distro"], []).append(data)
    return by_distro


def issue_body(distro: str, results: list[dict], missing: list[str], run_url: str = "") -> str:
    """The package-tests issue of a distribution."""
    failed = [(r["platform"], p) for r in sorted(results, key=lambda r: r["platform"])
              for p in r["packages"] if not p["ok"]]
    tested = sum(p.get("status") != "no-tests" for r in results for p in r["packages"])
    untested = sorted({(p["name"], p["build"]) for r in results for p in r["packages"] if p.get("status") == "no-tests"})
    flaky = [(r["platform"], p) for r in sorted(results, key=lambda r: r["platform"])
             for p in r["packages"] if p.get("status") == "flaky"]
    lines = [
        REPORT_MARKER,
        f"Nightly test of the published **{distro}** packages: the tests bundled in each package with a test file "
        f"(`shared/tests/`, `distros/{distro}/tests/`), run with `rattler-build test` against the newest "
        "dependencies from conda-forge, to catch breakages that come from conda-forge (e.g. ABI changes). "
        "robostack-bot updates this issue every night and closes it when every test passes.",
        "",
        f"**{len(failed)} of {tested} failed**" if failed else f"✅ **All {tested} passed.**",
        "",
    ]
    if missing:
        lines += [f"⚠️ No results for {', '.join(missing)} (the job failed before testing, see the workflow run).", ""]
    if failed:
        lines += ["| platform | package | build |", "|---|---|---|"]
        lines += [f"| {platform} | `{p['name']}` {p['version']} | `{p['build']}` |" for platform, p in failed]
        lines.append("")
        for platform, p in failed:
            lines += [f"<details><summary>{platform}: {p['name']} {p['build']}</summary>", "", "```text",
                      p.get("log", ""), "```", "", "</details>", ""]
    if flaky:
        lines += [("Passed only on the second try: "
                   + ", ".join(f"`{p['name']}` ({platform})" for platform, p in flaky)), ""]
    if untested:
        lines += [("Without bundled tests (built before their test file was added; tested again once rebuilt): "
                   + ", ".join(f"`{name}` (`{build}`)" for name, build in untested)), ""]
    if run_url:
        lines.append(f"[Workflow run]({run_url})")
    body = "\n".join(lines)
    if len(body) > MAX_ISSUE_BODY:
        body = body[:MAX_ISSUE_BODY] + "\n\n… (truncated, see the workflow run)"
    return body


def report(directory: Path, platforms: list[str], distros: list[str] | None = None) -> int:
    """Summarise the results and, in GitHub Actions, update each distribution's issue
    (of the given distributions, also those without any results)."""
    import maintenance  # only for the issue helpers

    run_url = ""
    if run_id := os.environ.get("GITHUB_RUN_ID"):
        run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{run_id}"
    failing = False
    by_distro = load_results(directory)
    for distro in sorted(set(distros or []) | set(by_distro)):
        results = by_distro.get(distro, [])
        missing = sorted(set(platforms) - {r["platform"] for r in results})
        failed = sum(not p["ok"] for r in results for p in r["packages"])
        bad = bool(failed or missing)
        failing |= bad
        body = issue_body(distro, results, missing, run_url)
        print(f"{distro}: {failed} failed" + (f", no results for {', '.join(missing)}" if missing else ""), flush=True)
        if os.environ.get("GITHUB_ACTIONS"):
            url = maintenance.publish_issue(maintenance._repository(), f"{distro}: package tests", REPORT_LABEL, body, bad)
            print(f"  {url or 'all passed, no issue to close'}", flush=True)
        else:
            print(body)
    return 1 if failing else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("select", help="list the package files that would be tested (JSON)")
    p.add_argument("--distro", required=True)
    p.add_argument("--platform", required=True)
    p = sub.add_parser("run", help="test them, writing the results")
    p.add_argument("--distro", required=True)
    p.add_argument("--platform", required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--package", action="append", help="only this package (repeatable; for local runs)")
    p = sub.add_parser("report", help="summarise results (and update the issues in GitHub Actions)")
    p.add_argument("directory", type=Path)
    p.add_argument("--platforms", default="linux-64 linux-aarch64 osx-64 osx-arm64 win-64",
                   help="platforms that should have results (default: all five)")
    p.add_argument("--distros", default="", help="distributions that should have results (default: those found)")
    ns = parser.parse_args()
    if ns.command == "select":
        print(json.dumps(select(ns.distro, ns.platform), indent=1))
        return 0
    if ns.command == "run":
        return run(ns.distro, ns.platform, ns.results, ns.package)
    return report(ns.directory, ns.platforms.split(), ns.distros.split())


if __name__ == "__main__":
    sys.exit(main())
