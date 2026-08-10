from __future__ import annotations

from pathlib import Path
from typing import Any

from giticizer.scoring.code_health import score_entities
from giticizer.vcs.git_reader import read_git_log_for_ref
from giticizer.vcs.parsers import parse_log


def run_pr_gate(repo: Path, base_ref: str, changed: set[str]) -> list[dict[str, Any]]:
    if not changed:
        return []

    base = parse_log(
        read_git_log_for_ref(
            repo,
            mode="git2",
            ref=base_ref,
            no_merges=False,
            excludes=[],
        ),
        mode="git2",
    )
    head = parse_log(
        read_git_log_for_ref(
            repo,
            mode="git2",
            ref="HEAD",
            no_merges=False,
            excludes=[],
        ),
        mode="git2",
    )

    head_scores = {
        r["entity"]: float(r["risk-score"]) for r in score_entities(head) if r["entity"] in changed
    }
    base_scores = {
        r["entity"]: float(r["risk-score"]) for r in score_entities(base) if r["entity"] in changed
    }

    rows = []
    for entity in sorted(changed):
        before = base_scores.get(entity, 0.0)
        after = head_scores.get(entity, before)
        rows.append(
            {
                "entity": entity,
                "base-risk": round(before, 2),
                "head-risk": round(after, 2),
                "delta-score": round(after - before, 2),
            }
        )
    rows.sort(key=lambda r: (-float(r["delta-score"]), str(r["entity"])))
    return rows
