from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from giticizer.models import Commit, FileChange

Row = dict[str, Any]


def _files(commits: list[Commit]) -> list[tuple[Commit, FileChange]]:
    return [(c, f) for c in commits for f in c.files]


def _sum(c: Commit) -> tuple[int, int]:
    return sum(f.added for f in c.files), sum(f.deleted for f in c.files)


def _sorted(rows: list[Row], key: Any) -> list[Row]:
    rows.sort(key=key)
    return rows


def summary(commits: list[Commit]) -> list[Row]:
    changed = _files(commits)
    return [
        {"statistic": "number-of-commits", "value": len(commits)},
        {"statistic": "number-of-entities", "value": len({f.path for _, f in changed})},
        {"statistic": "number-of-entities-changed", "value": len(changed)},
        {"statistic": "number-of-authors", "value": len({c.author for c in commits})},
    ]


def revisions(commits: list[Commit]) -> list[Row]:
    return [
        {"rev": c.rev, "date": c.date.isoformat(), "author": c.author, "n-entities": len(c.files)}
        for c in commits
    ]


def authors(commits: list[Commit], min_revs: int = 5) -> list[Row]:
    revs, auth = Counter(), defaultdict(set)
    for c, f in _files(commits):
        revs[f.path] += 1
        auth[f.path].add(c.author)
    rows = [
        {"entity": e, "n-authors": len(auth[e]), "n-revs": revs[e]}
        for e in revs
        if revs[e] >= min_revs
    ]
    return _sorted(rows, lambda r: (-int(r["n-authors"]), -int(r["n-revs"]), str(r["entity"])))


def coupling(
    commits: list[Commit],
    *,
    min_shared_revs: int = 5,
    min_coupling: int = 30,
    max_coupling: int = 100,
    max_changeset_size: int = 30,
    verbose: bool = False,
) -> list[Row]:
    revs, shared = Counter(), Counter()
    for c in commits:
        fs = sorted({f.path for f in c.files})
        if not fs or len(fs) > max_changeset_size:
            continue
        revs.update(fs)
        shared.update(itertools.combinations(fs, 2))
    rows: list[Row] = []
    for (a, b), n in shared.items():
        if n < min_shared_revs:
            continue
        for src, dst in ((a, b), (b, a)):
            deg = int((n / revs[src]) * 100) if revs[src] else 0
            if not (min_coupling <= deg <= max_coupling):
                continue
            row: Row = {
                "entity": src,
                "coupled": dst,
                "degree": deg,
                "average-revs": round((revs[src] + revs[dst]) / 2, 2),
                "shared-revs": n,
            }
            if verbose:
                row |= {"entity-revs": revs[src], "coupled-revs": revs[dst]}
            rows.append(row)
    return _sorted(rows, lambda r: (-int(r["degree"]), str(r["entity"]), str(r["coupled"])))


def age(commits: list[Commit], age_time_now: date | None = None) -> list[Row]:
    now, last = age_time_now or date.today(), {}
    for c, f in _files(commits):
        last[f.path] = max(c.date, last.get(f.path, c.date))
    return _sorted(
        [{"entity": e, "age-months": (now - d).days // 30} for e, d in last.items()],
        lambda r: (int(r["age-months"]), str(r["entity"])),
    )


def abs_churn(commits: list[Commit]) -> list[Row]:
    by = defaultdict(lambda: (0, 0))
    for c in commits:
        a, d = _sum(c)
        x, y = by[c.date.isoformat()]
        by[c.date.isoformat()] = (x + a, y + d)
    return _sorted(
        [{"date": k, "added": v[0], "deleted": v[1]} for k, v in by.items()],
        lambda r: str(r["date"]),
    )


def author_churn(commits: list[Commit]) -> list[Row]:
    by = defaultdict(lambda: (0, 0))
    for c in commits:
        a, d = _sum(c)
        x, y = by[c.author]
        by[c.author] = (x + a, y + d)
    return _sorted(
        [{"author": k, "added": v[0], "deleted": v[1]} for k, v in by.items()],
        lambda r: (-int(r["added"]), str(r["author"])),
    )


def entity_churn(commits: list[Commit]) -> list[Row]:
    by = defaultdict(lambda: (0, 0))
    for _, f in _files(commits):
        x, y = by[f.path]
        by[f.path] = (x + f.added, y + f.deleted)
    rows = [{"entity": k, "added": v[0], "deleted": v[1]} for k, v in by.items()]
    return _sorted(rows, lambda r: (-(int(r["added"]) + int(r["deleted"])), str(r["entity"])))


def entity_ownership(commits: list[Commit]) -> list[Row]:
    by = defaultdict(lambda: (0, 0))
    for c, f in _files(commits):
        x, y = by[(f.path, c.author)]
        by[(f.path, c.author)] = (x + f.added, y + f.deleted)
    rows = [{"entity": e, "author": a, "added": v[0], "deleted": v[1]} for (e, a), v in by.items()]
    return _sorted(rows, lambda r: (str(r["entity"]), -(int(r["added"]) + int(r["deleted"]))))


def entity_effort(commits: list[Commit]) -> list[Row]:
    total, per = Counter(), Counter()
    for c in commits:
        touched = {f.path for f in c.files}
        total.update(touched)
        per.update((e, c.author) for e in touched)
    rows = [
        {"entity": e, "author": a, "author-revs": n, "total-revs": total[e]}
        for (e, a), n in per.items()
    ]
    return _sorted(rows, lambda r: (str(r["entity"]), -int(r["author-revs"]), str(r["author"])))


def main_dev(commits: list[Commit]) -> list[Row]:
    grp: dict[str, list[Row]] = defaultdict(list)
    for r in entity_effort(commits):
        grp[str(r["entity"])].append(r)
    rows = []
    for e, rs in grp.items():
        w = max(rs, key=lambda r: int(r["author-revs"]))
        t = int(w["total-revs"]) or 1
        rows.append(
            {
                "entity": e,
                "main-dev": w["author"],
                "ownership": round((int(w["author-revs"]) / t) * 100, 2),
            }
        )
    return _sorted(rows, lambda r: (-float(r["ownership"]), str(r["entity"])))


def main_dev_by_revs(commits: list[Commit]) -> list[Row]:
    return main_dev(commits)


def communication(commits: list[Commit]) -> list[Row]:
    by, pairs = defaultdict(set), Counter()
    for c, f in _files(commits):
        by[f.path].add(c.author)
    for s in by.values():
        pairs.update(itertools.combinations(sorted(s), 2))
    rows = [{"author": a, "peer": b, "shared-entities": n} for (a, b), n in pairs.items()]
    return _sorted(rows, lambda r: (-int(r["shared-entities"]), str(r["author"]), str(r["peer"])))


def fragmentation(commits: list[Commit]) -> list[Row]:
    rows = [
        {**r, "fragmentation": round((int(r["n-authors"]) / (int(r["n-revs"]) or 1)) * 100, 2)}
        for r in authors(commits, 1)
    ]
    return _sorted(rows, lambda r: (-float(r["fragmentation"]), str(r["entity"])))


def soc(commits: list[Commit]) -> list[Row]:
    return main_dev(commits)


def messages(commits: list[Commit], expression: str | None = None) -> list[Row]:
    p = re.compile(expression, re.I) if expression else None
    return [
        {"rev": c.rev, "date": c.date.isoformat(), "author": c.author, "message": c.message}
        for c in commits
        if not p or p.search(c.message)
    ]


def identity(commits: list[Commit]) -> list[Row]:
    return [
        {
            "rev": c.rev,
            "date": c.date.isoformat(),
            "author": c.author,
            "entity": f.path,
            "added": f.added,
            "deleted": f.deleted,
            "message": c.message,
        }
        for c, f in _files(commits)
    ]


def refactoring_main_dev(commits: list[Commit]) -> list[Row]:
    p = re.compile(r"\b(refactor|cleanup|restructure|rename)\b", re.I)
    return main_dev([c for c in commits if p.search(c.message)])
