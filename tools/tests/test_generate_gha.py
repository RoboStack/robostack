"""rs <distro> gha: larger batches when the generated workflow is too large for GitHub."""

import robostack as rs


def test_gha_retries_with_larger_batches_when_the_workflow_is_too_large(monkeypatch, tmp_path):
    sizes = []

    def fake_run_tee(cmd, cwd):
        sizes.append(int(cmd[cmd.index("--batch_size") + 1]))
        if sizes[-1] < 50:
            return 1, b"RuntimeError: Generated workflow win.yml is 530.8 KiB, exceeding the 500 KiB limit."
        return 0, b""

    monkeypatch.setattr(rs, "run_tee", fake_run_tee)
    monkeypatch.setattr(rs, "work_dir", lambda distro: tmp_path)

    assert rs.generate_gha("jazzy", ["--platform", "win-64", "--batch-size", "25"]) == 0
    assert sizes == [25, 37, 55]


def test_gha_does_not_retry_other_failures(monkeypatch, tmp_path):
    sizes = []

    def fake_run_tee(cmd, cwd):
        sizes.append(int(cmd[cmd.index("--batch_size") + 1]))
        return 1, b"some other error"

    monkeypatch.setattr(rs, "run_tee", fake_run_tee)
    monkeypatch.setattr(rs, "work_dir", lambda distro: tmp_path)

    assert rs.generate_gha("jazzy", ["--platform", "win-64"]) == 1
    assert sizes == [25]


def test_gha_uses_the_distributions_anaconda_token(monkeypatch, tmp_path):
    work, root = tmp_path / "work", tmp_path / "root"
    work.mkdir(); (root / ".github" / "workflows").mkdir(parents=True)

    def fake_run_tee(cmd, cwd):
        (work / "linux.yml").write_text(
            "name: build\njobs:\n  stage_0:\n    permissions:\n      id-token: write\n    env:\n"
            "      ANACONDA_API_TOKEN: ${{ secrets.ANACONDA_API_TOKEN }}\n")
        return 0, b""

    monkeypatch.setattr(rs, "run_tee", fake_run_tee)
    monkeypatch.setattr(rs, "work_dir", lambda distro: work)
    monkeypatch.setattr(rs, "ROOT", root)

    assert rs.generate_gha("lyrical", ["--platform", "linux-64"]) == 0
    text = (root / ".github" / "workflows" / "build.yaml").read_text()
    assert "ANACONDA_API_TOKEN: ${{ secrets.ANACONDA_API_TOKEN_LYRICAL }}" in text
    assert "secrets.ANACONDA_API_TOKEN }}" not in text
