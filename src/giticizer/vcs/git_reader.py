from __future__ import annotations

import subprocess
from pathlib import Path


def read_git_log(
    repo: Path,
    *,
    mode: str,
    after: str | None,
    no_merges: bool,
    excludes: list[str],
) -> str:
    if mode not in {"git", "git2"}:
        raise ValueError(f"Unsupported mode: {mode}")

    cmd = ["git", "log", "--numstat", "--date=short"]

    if mode == "git2":
        cmd.append("--pretty=format:--%H--%ad--%aN--%s")
        cmd.append("--no-renames")
        cmd.append("--all")
    else:
        cmd.append("--pretty=format:[%h] %aN %ad %s")

    if no_merges:
        cmd.append("--no-merges")

    if after:
        cmd.append(f"--after={after}")

    if excludes:
        cmd.extend(["--", "."])
        cmd.extend(f":(exclude){item}" for item in excludes)

    completed = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def read_git_log_for_ref(
    repo: Path,
    *,
    mode: str,
    ref: str,
    no_merges: bool,
    excludes: list[str],
) -> str:
    if mode not in {"git", "git2"}:
        raise ValueError(f"Unsupported mode: {mode}")

    cmd = ["git", "log", ref, "--numstat", "--date=short"]

    if mode == "git2":
        cmd.append("--pretty=format:--%H--%ad--%aN--%s")
        cmd.append("--no-renames")
    else:
        cmd.append("--pretty=format:[%h] %aN %ad %s")

    if no_merges:
        cmd.append("--no-merges")

    if excludes:
        cmd.extend(["--", "."])
        cmd.extend(f":(exclude){item}" for item in excludes)

    completed = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def changed_files_against_base(repo: Path, base_ref: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo,
        text=True,
        check=True,
        capture_output=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
