from __future__ import annotations

import subprocess
from pathlib import Path


def read_git_log(
    repo: Path,
    *,
    mode: str,
    after: str | None,
    no_merges: bool,
    include_dirs: list[str],
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

    _append_pathspecs(cmd, repo=repo, include_dirs=include_dirs, excludes=excludes)

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
    include_dirs: list[str],
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

    _append_pathspecs(cmd, repo=repo, include_dirs=include_dirs, excludes=excludes)

    completed = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def changed_files_against_base(
    repo: Path,
    base_ref: str,
    *,
    include_dirs: list[str],
    excludes: list[str],
) -> list[str]:
    cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
    _append_pathspecs(cmd, repo=repo, include_dirs=include_dirs, excludes=excludes)
    completed = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        check=True,
        capture_output=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _append_pathspecs(
    cmd: list[str],
    *,
    repo: Path,
    include_dirs: list[str],
    excludes: list[str],
) -> None:
    if not include_dirs and not excludes:
        return

    normalized_includes = [_normalize_include_dir(repo, item) for item in include_dirs if item]
    cmd.append("--")
    if normalized_includes:
        cmd.extend(normalized_includes)
    else:
        cmd.append(".")
    cmd.extend(f":(exclude){item}" for item in excludes)


def _normalize_include_dir(repo: Path, include_dir: str) -> str:
    repo_root = repo.resolve()
    raw = include_dir.strip()
    if not raw:
        return "."

    # First try interpreting the value as repo-relative.
    repo_relative_candidate = (repo_root / raw).resolve()
    if repo_relative_candidate.is_relative_to(repo_root):
        rel = repo_relative_candidate.relative_to(repo_root).as_posix()
        return rel or "."

    # Accept absolute or shell-cwd-relative inputs when they still point inside the repo.
    cwd_candidate = (Path.cwd() / raw).resolve()
    if cwd_candidate.is_relative_to(repo_root):
        rel = cwd_candidate.relative_to(repo_root).as_posix()
        return rel or "."

    # Support values like "../<repo-name>/subdir" by stripping repo-name prefix.
    rel_from_repo_name = _strip_repo_name_prefix(raw, repo_root.name)
    if rel_from_repo_name is not None:
        prefixed = (repo_root / rel_from_repo_name).resolve()
        if prefixed.is_relative_to(repo_root):
            return rel_from_repo_name or "."

    raise ValueError(
        f"include-dir '{include_dir}' is outside repository '{repo_root}'. "
        "Use a path inside the selected repo, e.g. --include-dir src or select the right --repo."
    )


def _strip_repo_name_prefix(value: str, repo_name: str) -> str | None:
    parts = [p for p in Path(value).parts if p not in {"", ".", ".."}]
    if not parts or parts[0] != repo_name:
        return None
    if len(parts) == 1:
        return "."
    return Path(*parts[1:]).as_posix()
