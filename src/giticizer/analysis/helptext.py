from __future__ import annotations

ANALYSIS_INFO: dict[str, dict[str, str]] = {
    "summary": {
        "meaning": "High-level repository totals for commits, entities, and authors.",
        "useful": (
            "Useful as a quick sanity check before deeper analysis and for "
            "reporting overall scale."
        ),
    },
    "revisions": {
        "meaning": "Per-commit revision listing with author, date, and entities touched.",
        "useful": (
            "Useful for timeline audits and understanding commit granularity "
            "and activity cadence."
        ),
    },
    "authors": {
        "meaning": "Number of distinct authors and revision count per entity.",
        "useful": (
            "Useful for spotting coordination-heavy files and potential "
            "communication bottlenecks."
        ),
    },
    "coupling": {
        "meaning": "Logical coupling between entities that frequently change together.",
        "useful": "Useful for identifying hidden dependencies and refactoring candidates.",
    },
    "age": {
        "meaning": "Age in months since each entity's last change.",
        "useful": (
            "Useful for separating stable areas from volatile code and "
            "prioritizing modernization."
        ),
    },
    "abs-churn": {
        "meaning": "Total lines added and deleted by date.",
        "useful": (
            "Useful for detecting activity spikes and periods of high "
            "development turbulence."
        ),
    },
    "author-churn": {
        "meaning": "Lines added/deleted aggregated by author.",
        "useful": "Useful for contribution pattern analysis and balancing knowledge distribution.",
    },
    "entity-churn": {
        "meaning": "Lines added/deleted aggregated by entity.",
        "useful": "Useful for finding high-churn hotspots that likely need design attention.",
    },
    "entity-ownership": {
        "meaning": "Per-entity contribution split by author in added/deleted lines.",
        "useful": "Useful for ownership visibility, onboarding planning, and resilience analysis.",
    },
    "entity-effort": {
        "meaning": "Per-entity revision effort split by author.",
        "useful": "Useful for identifying who is most active in each area of the codebase.",
    },
    "main-dev": {
        "meaning": "Main developer per entity based on revision ownership percentage.",
        "useful": "Useful for bus-factor checks and review routing.",
    },
    "main-dev-by-revs": {
        "meaning": "Main developer per entity by revision ownership (same lens as main-dev).",
        "useful": (
            "Useful when you prefer a revision-based ownership view for "
            "planning and support."
        ),
    },
    "messages": {
        "meaning": "Commit message stream, optionally filtered by regex.",
        "useful": (
            "Useful for mining intent signals like bug-fix, refactor, or "
            "release-related activity."
        ),
    },
    "refactoring-main-dev": {
        "meaning": "Main developer view restricted to refactoring-like commits.",
        "useful": "Useful for understanding who is driving structural change.",
    },
    "identity": {
        "meaning": "Flat intermediate event stream of revision, author, entity, and churn values.",
        "useful": "Useful for debugging parser assumptions and exporting raw facts to other tools.",
    },
    "communication": {
        "meaning": "Co-work relationships between authors via shared entities.",
        "useful": "Useful for mapping collaboration networks and coordination hotspots.",
    },
    "fragmentation": {
        "meaning": "Author spread per entity relative to revision count.",
        "useful": "Useful for spotting areas with fragmented ownership.",
    },
    "soc": {
        "meaning": "Socio-technical proxy derived from ownership signals.",
        "useful": (
            "Useful for quick socio-technical risk scanning when full models "
            "are unavailable."
        ),
    },
    "code-health": {
        "meaning": (
            "Heuristic quality score that combines churn, ownership, and "
            "collaboration factors."
        ),
        "useful": "Useful for prioritizing risky files and tracking maintainability trends.",
    },
    "action-items": {
        "meaning": (
            "Prioritized, explainable recommendations derived from behavioral risk "
            "signals for each entity."
        ),
        "useful": (
            "Useful for turning analysis into concrete next actions during planning, "
            "triage, and PR review."
        ),
    },
}


def render_analysis_help(name: str) -> str:
    info = ANALYSIS_INFO.get(name)
    if not info:
        return "No description available."
    return f"Meaning: {info['meaning']}\nUseful: {info['useful']}"


def render_all_analysis_help(names: list[str]) -> str:
    lines = []
    for name in sorted(names):
        info = ANALYSIS_INFO.get(name)
        if info is None:
            lines.append(f"- {name}: No description available.")
            continue
        lines.append(f"- {name}: {info['meaning']} Useful: {info['useful']}")
    return "\n".join(lines)
