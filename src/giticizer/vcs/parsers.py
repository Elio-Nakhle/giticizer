from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import TypedDict

from giticizer.models import Commit, FileChange

GIT_HEADER = re.compile(
    r"^\[(?P<rev>[^\]]+)\] (?P<author>.+) (?P<date>\d{4}-\d{2}-\d{2}) (?P<msg>.*)$"
)


class ParsedCommit(TypedDict):
    rev: str
    date: str
    author: str
    msg: str
    files: list[FileChange]


def parse_log(raw: str, *, mode: str) -> list[Commit]:
    if mode not in {"git", "git2"}:
        raise ValueError(f"Unsupported mode: {mode}")
    commits: list[Commit] = []
    cur: ParsedCommit | None = None

    for line in raw.splitlines():
        header = _read_header(line, mode)
        if header:
            if cur:
                commits.append(_to_commit(cur))
            cur = {
                "rev": header[0],
                "date": header[1],
                "author": header[2],
                "msg": header[3],
                "files": [],
            }
            continue
        if not cur or not line.strip():
            continue
        fc = _parse_numstat(line)
        if fc:
            cur["files"].append(fc)

    if cur:
        commits.append(_to_commit(cur))
    return commits


def aggregate_daily(commits: list[Commit]) -> list[Commit]:
    grouped: dict[tuple[str, date], list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[(c.author, c.date)].append(c)
    out: list[Commit] = []
    for (author, d), chunk in grouped.items():
        files: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        msgs = []
        for c in chunk:
            if c.message:
                msgs.append(c.message)
            for f in c.files:
                a, x = files[f.path]
                files[f.path] = (a + f.added, x + f.deleted)
        merged = tuple(
            FileChange(path=p, added=v[0], deleted=v[1]) for p, v in sorted(files.items())
        )
        out.append(
            Commit(
                rev=f"daily:{author}:{d.isoformat()}:{len(chunk)}",
                author=author,
                date=d,
                message=" | ".join(msgs),
                files=merged,
            )
        )
    out.sort(key=lambda c: (c.date, c.author, c.rev))
    return out


def _read_header(line: str, mode: str) -> tuple[str, str, str, str] | None:
    if mode == "git2" and line.startswith("--") and line.count("--") >= 4:
        p = line.split("--", maxsplit=4)
        return (p[1], p[2], p[3], p[4]) if len(p) >= 5 else None
    if mode == "git":
        m = GIT_HEADER.match(line)
        if m:
            return m.group("rev"), m.group("date"), m.group("author"), m.group("msg")
    return None


def _parse_numstat(line: str) -> FileChange | None:
    p = line.split("\t")
    if len(p) != 3:
        return None
    a, d, path = p
    return FileChange(path=path, added=0 if a == "-" else int(a), deleted=0 if d == "-" else int(d))


def _to_commit(c: ParsedCommit) -> Commit:
    return Commit(
        rev=c["rev"],
        author=c["author"],
        date=date.fromisoformat(c["date"]),
        message=c["msg"],
        files=tuple(c["files"]),
    )
