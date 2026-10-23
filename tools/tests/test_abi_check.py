"""The ABI check's pull-request comment (no libabigail needed)."""

import abi_check
import robostack as rs


def _soname(dependents, checked=True):
    return {"verdict": "soname", "old": "1.0 (build 5)", "new": "1.1", "libraries": {"libfoo.so": {"verdict": "soname"}},
            "removed_libraries": [], "headers": [], "pins": [],
            "dependents": {"rebuild": dependents, "checked": checked, "candidates": len(dependents) + 2}}


def test_rebuild_snippet_lists_every_dependent_once_with_ros_names():
    results = {"foo": _soname(["bar-baz", "qux"]), "foo2": _soname(["qux"])}
    lines = abi_check.rebuild_snippet(results, "jazzy", 26)
    assert "distros/jazzy/pkg_additional_info.yaml" in lines[0]
    assert lines[lines.index("```yaml") + 1:lines.index("```", lines.index("```yaml") + 1)] == [
        "bar_baz:", "  build_number: 26", "qux:", "  build_number: 26"]


def test_no_snippet_without_dependents():
    assert abi_check.rebuild_snippet({"foo": _soname([])}, "jazzy", 26) == []
    assert abi_check.rebuild_snippet({"foo": _soname(["bar"])}, "jazzy", None) == []


def test_unchecked_dependents_get_a_hint():
    assert "couldn't be checked" in abi_check.rebuild_snippet({"foo": _soname(["bar"], checked=False)}, "jazzy", 26)[0]


def test_dependents_rebuilt_in_the_pull_request_need_no_bump():
    results = {"foo": _soname(["bar", "qux"]), "foo2": _soname(["bar"])}
    abi_check.drop_rebuilt(results, {"foo", "bar"})
    assert results["foo"]["dependents"]["rebuild"] == ["qux"]
    assert results["foo2"]["dependents"]["rebuild"] == []
    lines = abi_check.rebuild_snippet(results, "jazzy", 26)
    assert lines[lines.index("```yaml") + 1:lines.index("```", lines.index("```yaml") + 1)] == ["qux:", "  build_number: 26"]
    assert "1 more already rebuilt in this pull request: bar" in abi_check._row("foo", results["foo"])
    abi_check.drop_rebuilt(results, {"qux"})
    assert abi_check.rebuild_snippet(results, "jazzy", 26) == []


def test_summary_puts_the_snippet_under_the_table():
    results = {"foo": _soname(["bar"]),
               "ok": {"verdict": "compatible", "old": "1", "new": "2", "libraries": {}, "removed_libraries": [],
                      "headers": [], "pins": []}}
    text = "\n".join(abi_check.pr_summary(results, "jazzy", "linux-64", ["https://x/test", "https://x/jazzy"], 26))
    assert text.index("| foo |") < text.index("bar:\n  build_number: 26") < text.index("<details>", 1)
    assert "https://x/test/linux-64 and https://x/jazzy/linux-64" in text
    # one collapsed section per distribution, the count of breaking changes in its summary
    assert text.startswith("<details><summary><b>jazzy linux-64</b>: **1 need their dependents rebuilt**, "
                           "1 can be bumped on their own</summary>")
    assert text.rstrip().endswith("</details>")
    quiet = "\n".join(abi_check.pr_summary({"ok": results["ok"]}, "jazzy", "linux-64", "https://x/jazzy", 26))
    assert quiet.startswith("<details><summary><b>jazzy linux-64</b>: 1 can be bumped on their own</summary>")


def test_next_build_number_is_above_vinca_and_every_published_build(tmp_path, monkeypatch):
    (tmp_path / "jazzy").mkdir()
    (tmp_path / "jazzy" / "vinca.yaml").write_text("ros_distro: jazzy\nbuild_number: 25\n")
    monkeypatch.setattr(rs, "DISTROS", tmp_path)
    assert abi_check.next_build_number({"a": {"1": {"build_number": 30}}, "b": {"2": {"build_number": 7}}}, "jazzy") == 31
    assert abi_check.next_build_number({"a": {"1": {"build_number": 3}}}, "jazzy") == 26


def test_compatibility_packages_with_and_without_the_mutex():
    assert abi_check._is_compatibility_package({"depends": ["ros2-rclcpp ==28.1.22"]})
    assert abi_check._is_compatibility_package(
        {"depends": ["ros2-rclcpp ==28.1.22", "ros2-distro-mutex 0.19.* jazzy_*"]})
    assert not abi_check._is_compatibility_package(
        {"depends": ["ros2-rclcpp ==28.1.22", "libboost >=1.90"]})
    assert not abi_check._is_compatibility_package({"depends": ["ros2-distro-mutex 0.19.* jazzy_*", "libfoo"]})
    assert not abi_check._is_compatibility_package({"depends": []})


def test_pin_changes_separates_changed_new_and_dropped_dependencies():
    old = {"depends": ["libboost >=1.88.0,<1.89.0a0", "libboost-devel", "ros2-rclcpp", "openssl >=3.5,<4.0a0"]}
    new = {"depends": ["libboost >=1.90.0,<1.91.0a0", "libboost-devel", "ros2-rclcpp",
                       "eigen-abi >=5.0.1.80,<5.0.1.81.0a0", "eigen-abi-devel", "nlohmann_json"]}
    assert abi_check.pin_changes(old, new, "jazzy") == [
        "pins changed: libboost >=1.88.0,<1.89 → >=1.90.0,<1.91",
        "new dependencies: eigen-abi >=5.0.1.80,<5.0.1.81, nlohmann_json any",
        "dropped dependencies: openssl",
    ]
    assert abi_check.pin_changes(old, old, "jazzy") == []
