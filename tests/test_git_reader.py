from pathlib import Path
from subprocess import CompletedProcess

from giticizer.vcs import git_reader


def test_read_git_log_applies_include_and_exclude(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **_) -> CompletedProcess[str]:
        captured.append(cmd)
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(git_reader.subprocess, "run", fake_run)
    git_reader.read_git_log(
        Path("."),
        mode="git2",
        after=None,
        no_merges=False,
        include_dirs=["src"],
        excludes=["tests"],
    )

    assert captured
    cmd = captured[0]
    assert "--" in cmd
    assert "src" in cmd
    assert ":(exclude)tests" in cmd


def test_changed_files_applies_include_and_exclude(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **_) -> CompletedProcess[str]:
        captured.append(cmd)
        return CompletedProcess(cmd, 0, stdout="src/a.py\n", stderr="")

    monkeypatch.setattr(git_reader.subprocess, "run", fake_run)
    out = git_reader.changed_files_against_base(
        Path("."),
        "origin/main",
        include_dirs=["src"],
        excludes=["docs"],
    )

    assert out == ["src/a.py"]
    cmd = captured[0]
    assert "--" in cmd
    assert "src" in cmd
    assert ":(exclude)docs" in cmd
