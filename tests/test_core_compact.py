from datetime import date
from pathlib import Path

from giticizer.analysis import core
from giticizer.integrations.mapping import apply_group_mapping, validate_group_mapping
from giticizer.models import Commit, FileChange
from giticizer.scoring.code_health import score_entities
from giticizer.vcs.parsers import parse_log

COMMITS = [
    Commit(
        "a1",
        "Alice",
        date(2026, 8, 1),
        "feat",
        (FileChange("src/a.py", 10, 2), FileChange("src/b.py", 2, 1)),
    ),
    Commit("b1", "Bob", date(2026, 8, 2), "refactor", (FileChange("src/a.py", 1, 0),)),
]


def test_parse_and_summary() -> None:
    raw = "--abc--2026-08-01--A--m\n1\t0\tsrc/a.py\n"
    assert parse_log(raw, mode="git2")[0].rev == "abc"
    stats = {r["statistic"]: r["value"] for r in core.summary(COMMITS)}
    assert stats["number-of-commits"] == 2 and stats["number-of-authors"] == 2


def test_coupling_and_scoring() -> None:
    assert core.coupling(COMMITS, min_shared_revs=1, min_coupling=1)
    scored = score_entities(COMMITS)
    assert scored and "code-health" in scored[0] and "risk-score" in scored[0]


def test_mapping(tmp_path: Path) -> None:
    m = tmp_path / "map.txt"
    m.write_text(r"^src/a\.py$ => Core", encoding="utf-8")
    mapped = apply_group_mapping(COMMITS, m)
    assert any(f.path == "Core" for c in mapped for f in c.files)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")
    stats = {r["statistic"]: r["value"] for r in validate_group_mapping(tmp_path, m)}
    assert stats["rules"] == 1 and stats["files-total"] >= 1
