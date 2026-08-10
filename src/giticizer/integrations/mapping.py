from __future__ import annotations

import re
from pathlib import Path

from giticizer.models import Commit, FileChange


def _load_mapping(mapping_file: Path) -> list[tuple[re.Pattern[str], str]]:
    rules = []
    for raw in mapping_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=>" not in line:
            continue
        pattern, group = [p.strip() for p in line.split("=>", 1)]
        rules.append((re.compile(pattern), group))
    return rules


def apply_group_mapping(commits: list[Commit], mapping_file: Path) -> list[Commit]:
    rules = _load_mapping(mapping_file)
    out = []
    for c in commits:
        files = []
        for fc in c.files:
            mapped = next((g for p, g in rules if p.search(fc.path)), fc.path)
            files.append(FileChange(path=mapped, added=fc.added, deleted=fc.deleted))
        out.append(
            Commit(rev=c.rev, author=c.author, date=c.date, message=c.message, files=tuple(files))
        )
    return out


def validate_group_mapping(repo: Path, mapping_file: Path) -> list[dict[str, object]]:
    rules = _load_mapping(mapping_file)
    paths = [p.as_posix() for p in repo.rglob("*") if p.is_file() and ".git/" not in p.as_posix()]
    matched = {p for p in paths if any(rx.search(p) for rx, _ in rules)}
    return [
        {"statistic": "rules", "value": len(rules)},
        {"statistic": "files-total", "value": len(paths)},
        {"statistic": "files-matched", "value": len(matched)},
        {"statistic": "files-unmatched", "value": len(paths) - len(matched)},
    ]
