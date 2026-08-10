from __future__ import annotations

from typing import Any

from giticizer.analysis import core
from giticizer.models import Commit
from giticizer.scoring.code_health import score_entities


def action_items(commits: list[Commit]) -> list[dict[str, Any]]:
    scored = score_entities(commits)
    ownership = {r["entity"]: float(r["ownership"]) for r in core.main_dev(commits)}
    owners = {r["entity"]: str(r["main-dev"]) for r in core.main_dev(commits)}

    rows: list[dict[str, Any]] = []
    for row in scored:
        entity = str(row["entity"])
        risk = float(row["risk-score"])
        factors = {
            "churn": float(row["churn-factor"]),
            "ownership": float(row["ownership-factor"]),
            "collaboration": float(row["collaboration-factor"]),
        }
        primary = max(factors.items(), key=lambda item: item[1])[0]
        owner_pct = ownership.get(entity, 100.0)

        if primary == "churn":
            action = "Split and stabilize high-churn hotspot"
            impact = "Lower change failure risk through smaller, safer changes"
        elif primary == "ownership":
            action = "Broaden ownership with pair reviews and rotations"
            impact = "Reduce key-person dependency and improve resilience"
        else:
            action = "Clarify module boundaries and reduce coordination overhead"
            impact = "Decrease cross-author friction and rework"

        priority = min(100.0, risk + max(0.0, 70.0 - owner_pct) * 0.4)

        rows.append(
            {
                "entity": entity,
                "priority-score": round(priority, 2),
                "primary-risk": primary,
                "recommended-action": action,
                "expected-impact": impact,
                "owner-hint": owners.get(entity, "n/a"),
            }
        )

    rows.sort(key=lambda r: (-float(r["priority-score"]), str(r["entity"])))
    return rows
