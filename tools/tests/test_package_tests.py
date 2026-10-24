import json

import package_tests


def record(name, version, build, number, timestamp=0):
    return {"name": name, "version": version, "build": build, "build_number": number, "timestamp": timestamp}


def test_tested_packages_are_the_test_files(tmp_path, monkeypatch):
    (tmp_path / "shared" / "tests").mkdir(parents=True)
    (tmp_path / "distros" / "jazzy" / "tests").mkdir(parents=True)
    (tmp_path / "shared" / "tests" / "ros2-rclpy.yaml").write_text("tests: []\n")
    (tmp_path / "shared" / "tests" / "ros2-std-msgs").mkdir()  # the files a test uses
    (tmp_path / "distros" / "jazzy" / "tests" / "ros2-rcutils.yaml").write_text("tests: []\n")
    monkeypatch.setattr(package_tests.rs, "ROOT", tmp_path)
    monkeypatch.setattr(package_tests.rs, "DISTROS", tmp_path / "distros")
    assert package_tests.tested_packages("jazzy") == ["ros2-rclpy", "ros2-rcutils"]
    assert package_tests.tested_packages("humble") == ["ros2-rclpy"]


def test_newest_builds_keeps_every_variant_of_the_newest_build():
    repodata = {
        "packages.conda": {
            "a-1-py312_25.conda": record("ros2-a", "1", "py312_25", 25, 1),
            "a-1-py314_27.conda": record("ros2-a", "1", "py314_27", 27, 2),
            "a-1-py313_27.conda": record("ros2-a", "1", "py313_27", 27, 3),
            "b-2-h1_3.conda": record("ros2-b", "2", "h1_3", 3),
            "c-1-h_1.conda": record("ros2-untested", "1", "h_1", 1),
        },
        # the same build in the old format too: the .conda one is tested
        "packages": {"a-1-py314_27.tar.bz2": record("ros2-a", "1", "py314_27", 27, 2)},
    }
    selected = package_tests.newest_builds(repodata, ["ros2-a", "ros2-b"])
    assert [(r["name"], r["build"], r["fn"]) for r in selected] == [
        ("ros2-a", "py313_27", "a-1-py313_27.conda"),
        ("ros2-a", "py314_27", "a-1-py314_27.conda"),
        ("ros2-b", "h1_3", "b-2-h1_3.conda"),
    ]
    assert package_tests.newest_builds({}, ["ros2-a"]) == []


def test_ran_test_counts_the_tests_rattler_build_ran():
    log = ["Testing commands:", "✔ python imports test passed!", "✔ package contents test passed!",
           "✔ all tests passed!", "✔ Successfully updated the test environment"]
    assert sum(bool(package_tests.RAN_TEST.search(line)) for line in log) == 3


def test_issue_body_lists_failures_and_untested_builds():
    results = [
        {"distro": "jazzy", "platform": "win-64", "packages": [
            {"name": "ros2-a", "version": "1", "build": "h_27", "ok": False, "status": "failed", "log": "boom"},
            {"name": "ros2-b", "version": "2", "build": "h_25", "ok": True, "status": "no-tests"},
            {"name": "ros2-c", "version": "3", "build": "h_27", "ok": True, "status": "flaky"},
        ]},
        {"distro": "jazzy", "platform": "linux-64", "packages": [
            {"name": "ros2-a", "version": "1", "build": "h_27", "ok": True, "status": "passed"},
        ]},
    ]
    body = package_tests.issue_body("jazzy", results, ["osx-64"], "https://run")
    assert "**1 of 3 failed**" in body and "second try: `ros2-c` (win-64)" in body
    assert "| win-64 | `ros2-a` 1 | `h_27` |" in body and "boom" in body
    assert "`ros2-b` (`h_25`)" in body and "No results for osx-64" in body
    assert body.endswith("[Workflow run](https://run)")
    clean = package_tests.issue_body("jazzy", results[1:], [])
    assert "All 1 passed" in clean and "|---|" not in clean


def test_report_includes_distributions_without_results(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "package-tests-jazzy-linux-64").mkdir()
    (tmp_path / "package-tests-jazzy-linux-64" / "jazzy-linux-64.json").write_text(json.dumps(
        {"distro": "jazzy", "platform": "linux-64",
         "packages": [{"name": "ros2-a", "version": "1", "build": "h_1", "ok": True, "status": "passed"}]}))
    assert package_tests.report(tmp_path, ["linux-64"], ["jazzy"]) == 0
    # humble's jobs failed before writing results: reported, and the run fails
    assert package_tests.report(tmp_path, ["linux-64"], ["humble", "jazzy"]) == 1
    assert "humble: 0 failed, no results for linux-64" in capsys.readouterr().out
