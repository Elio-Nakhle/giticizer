from __future__ import annotations

from typing import Any

from giticizer.analysis import core
from giticizer.models import Commit


# Open, explainable heuristic that approximates a CodeScene-like health score.
def score_entities(commits: list[Commit]) -> list[dict[str, Any]]:
    churn = {r["entity"]: r["added"] + r["deleted"] for r in core.entity_churn(commits)}
    ownership = {r["entity"]: r["ownership"] for r in core.main_dev(commits)}
    author_count = {r["entity"]: r["n-authors"] for r in core.authors(commits, min_revs=1)}
    entities = sorted(set(churn) | set(ownership) | set(author_count))

    max_churn = max(churn.values(), default=1)
    rows = []
    for e in entities:
        churn_score = (churn.get(e, 0) / max_churn) * 60
        bus_risk = (100 - float(ownership.get(e, 100))) * 0.25
        collab_risk = min(int(author_count.get(e, 1)) * 5, 15)
        risk = round(min(100.0, churn_score + bus_risk + collab_risk), 2)
        rows.append(
            {
                "entity": e,
                "code-health": round(100 - risk, 2),
                "risk-score": risk,
                "churn-factor": round(churn_score, 2),
                "ownership-factor": round(bus_risk, 2),
                "collaboration-factor": collab_risk,
            }
        )
    rows.sort(key=lambda r: (r["code-health"], r["entity"]))
    return rows
