---
name: robostack-ci-triage
description: Triage failing RoboStack pull-request CI (testpr.yaml "Build" runs), especially robostack-bot rosdistro-sync and pinning PRs - read job states, pull and search logs, map failures to fixes, and decide when to push without cancelling running builds. Use when a PR check fails, when babysitting a bot PR, or before pushing to a PR whose builds are running.
---

# Triage pull-request CI

The fixing itself is in `robostack-debug-build` and `robostack-patch`; this is how to
get from a red check to the right failure, and how to push fixes without wasting
hours of runner time. `<d>` is the distribution, `<pr>` the pull request number.

## 1. Read job states (never trust `gh pr checks` alone)

`gh pr checks` prints a running job as `pending 0`, the same as a queued one. Ask the
run instead:

```bash
run=$(gh run list -R RoboStack/robostack --branch <pr-branch> --workflow testpr.yaml \
      --limit 1 --json databaseId,headSha -q '.[0].databaseId')
gh run view "$run" -R RoboStack/robostack \
  --json headSha,jobs -q '.headSha, (.jobs[] | "\(.databaseId) \(.name) \(.status) \(.conclusion) \(.startedAt)")'
```

Compare `headSha` with the PR head: a failure from a head you already replaced is
stale. Jobs are named `<d> patches`, `<d> <platform>`, plus `check` and `plan`.

## 2. Pull the log and find the real error

```bash
mkdir -p ~/robot/robostack/logs/pr<pr>   # any durable place, not /tmp
gh api repos/RoboStack/robostack/actions/jobs/<job-id>/logs > <file>.log
grep -nE "× error|error:|CMake Error|undefined reference|error C[0-9]{4}|error LNK" <file>.log \
  | grep -vE "wxCONV_FAILED|COMPILE_WARNING_AS_ERROR" | tail -40
```

- A build log is often >500k lines; search from the end. rattler-build's `× error`
  block names the failing package (`rattler-build_ros2-<pkg>_...`) and its work dir,
  and the compiler error is a few lines above it.
- The run's summary page (`gh run view <run> -R RoboStack/robostack`, or the web UI)
  lists built and failed packages per job (`tools/summarize_rattler_build.py`); the
  full `rattler-build.log` is also uploaded as the `build-log-<d>-<platform>-...`
  artifact.
- Noise that is not the failure: wxWidgets `wxCONV_FAILED` warnings, "Ignoring
  COMPILE_WARNING_AS_ERROR" lines, and `FAILED` inside other packages' warnings.
- `<d> patches` failing means a patch no longer applies to a new upstream version:
  refresh it (`robostack-patch`), then `pixi run rs <d> check-patches --recipe ros2-<pkg>`.
- `check` failing: run `pixi run rs check` locally (stale generated files, unsorted
  YAML), then `git checkout -- pixi.lock` if it touched the lock file.

## 3. Map the failure to a fix

| symptom | usual cause / fix |
|---|---|
| fails only on one platform after a version bump in a sync PR | new upstream code meets a stricter compiler; patch the source, keep it upstream-able |
| clang: `no matching function` / `cannot convert initializer list argument` to a ROS message type | `{}` for a message argument; ROS messages have an `explicit` default constructor, so GCC accepts it and clang doesn't. Pass `std_msgs::msg::Header()` etc. |
| MSVC `warning C4xxx` reported as an error | the project's own `/WX` (it wins over `--compile-no-warning-as-error`); fix the code (e.g. C4864: add `template` in `x.template cast<T>()`) or drop `/WX` in a patch |
| Windows `could not find any instance of Visual Studio` | the runner image doesn't have the MSVC the distribution pins (`c_compiler` in `distros/<d>/conda_build_config.yaml`): `vs2022` needs windows-2022, `vs` (VS 2026) windows-2025 (RoboStack/robostack#255 picks the image per distribution) |
| Windows `The CXX compiler identification is unknown`, MSB4018 `IndexOutOfRangeException` in FileTracker | MSBuild 18 with an empty `LocalApplicationData` because rattler-build's strict env isolation sets `USERPROFILE` to the work dir; build with `--env-isolation conda-build` (RoboStack/robostack#255) |
| missing enum / symbol from a conda-forge library | the library's version is pinned or overridden too old (check `override_version` in `pkg_additional_info.yaml` and `shared/pinning/`) |
| gtest / test code in a library build fails | tests are built although they're not run; guard them with `BUILD_TESTING` / an option in a patch, or fix the test |
| Linux/macOS job ends near 6 h without a package error | `tools/ci_build.py` stopped before the job limit and saved the cache; the next run continues from there. Not a failure to fix |

For a CMake configure failure on Windows, the `CMakeConfigureLog.yaml` /
`CMakeError.log` of the work dir has the real reason; the console log only says that
the configure step failed.

## 4. Push without cancelling good work

`testpr.yaml` has `cancel-in-progress: true`: **every push to the PR cancels all of its
running builds**, on every platform. The build cache is saved on cancel, so progress
isn't lost entirely, but a job that was 4 hours in restarts its unfinished packages.

Before pushing, check step 1:

- If only the failed platform is affected by your fix and other platforms are still
  building, commit locally and wait for them (or until one fails, which frees the
  push). Batch several fixes into one push.
- If the other running jobs will certainly hit the same failure (e.g. a clang error
  on osx-arm64 while osx-64 is still running), push right away.
- `build:<platform>` / `build:<d>` labels limit what the next run builds; adding a
  label doesn't start a run.
- After cancelling a run, wait a few minutes for its cache-save step before starting
  another one.
- If a package that was already built in the PR changes without a new build number
  (e.g. its patch changed after it succeeded), evict it: `evict_cache` in
  `distros/<d>/ci.yaml`.

Don't start extra CI runs to "see what happens"; reproduce locally with
`pixi run rs <d> build-one ros2-<pkg>` where the platform allows.

## 5. Sync PRs from robostack-bot

`update-rosdistro-snapshot` PRs bump many packages at once, so expect a few new
failures per platform, mostly in packages whose version changed: compare the tag in
`distros/<d>/rosdistro_snapshot.yaml` with `git diff origin/main`. Fix the package
rather than excluding it; exclusions need a reason in a comment (see
`robostack-package-selection`). Push to the bot's branch with
`git push origin HEAD:<bot-branch>`; never rebase or force-push it, merge `main` into
it on conflicts.
