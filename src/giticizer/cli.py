from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import typer

from giticizer.analysis import core
from giticizer.analysis.helptext import render_all_analysis_help, render_analysis_help
from giticizer.exporters.io import to_csv, to_json
from giticizer.integrations.mapping import apply_group_mapping, validate_group_mapping
from giticizer.integrations.pr_gate import run_pr_gate
from giticizer.scoring.action_items import action_items
from giticizer.scoring.code_health import score_entities
from giticizer.vcs.git_reader import changed_files_against_base, read_git_log
from giticizer.vcs.parsers import aggregate_daily, parse_log

app = typer.Typer(help="Behavioral code analysis for Git repositories")
Row = dict[str, Any]
AnalysisFn = Callable[..., list[Row]]

ANALYSES = {
    "summary": core.summary,
    "revisions": core.revisions,
    "authors": core.authors,
    "coupling": core.coupling,
    "age": core.age,
    "abs-churn": core.abs_churn,
    "author-churn": core.author_churn,
    "entity-churn": core.entity_churn,
    "entity-ownership": core.entity_ownership,
    "entity-effort": core.entity_effort,
    "main-dev": core.main_dev,
    "main-dev-by-revs": core.main_dev_by_revs,
    "messages": core.messages,
    "refactoring-main-dev": core.refactoring_main_dev,
    "identity": core.identity,
    "communication": core.communication,
    "fragmentation": core.fragmentation,
    "soc": core.soc,
    "code-health": score_entities,
    "action-items": action_items,
}

ANALYSIS_HELP = (
    "Analysis to run. Use 'giticizer analyses' for available analyses with meaning/usefulness, "
    "or 'giticizer explain-analysis --analysis <name>' for details."
)


def run() -> None:
    app()


@app.command()
def analyze(
    repo: Path = typer.Option(Path("."), "--repo", "-p"),
    analysis: str = typer.Option("authors", "--analysis", "-a", help=ANALYSIS_HELP),
    vcs_mode: str = typer.Option("git2", "--version-control", "-c"),
    after: str | None = typer.Option(None, "--after"),
    rows: int | None = typer.Option(None, "--rows", "-r"),
    output_format: str = typer.Option("csv", "--output-format"),
    output_file: Path | None = typer.Option(None, "--output-file"),
    group: Path | None = typer.Option(None, "--group", "-g"),
    min_revs: int = typer.Option(5, "--min-revs", "-n"),
    min_shared_revs: int = typer.Option(5, "--min-shared-revs", "-m"),
    min_coupling: int = typer.Option(30, "--min-coupling", "-i"),
    max_coupling: int = typer.Option(100, "--max-coupling", "-x"),
    max_changeset_size: int = typer.Option(30, "--max-changeset-size", "-s"),
    expression_to_match: str | None = typer.Option(None, "--expression-to-match", "-e"),
    temporal_period: bool = typer.Option(False, "--temporal-period", "-t"),
    age_time_now: str | None = typer.Option(None, "--age-time-now", "-d"),
    no_merges: bool = typer.Option(False, "--ignore-merges"),
    verbose_results: bool = typer.Option(False, "--verbose-results"),
    exclude: list[str] = typer.Option([], "--exclude"),
) -> None:
    if analysis not in ANALYSES:
        raise typer.BadParameter(f"Unsupported analysis '{analysis}'")
    if output_format not in {"csv", "json"}:
        raise typer.BadParameter("output-format must be one of: csv,json")

    commits = parse_log(
        read_git_log(repo, mode=vcs_mode, after=after, no_merges=no_merges, excludes=exclude),
        mode=vcs_mode,
    )
    if group:
        commits = apply_group_mapping(commits, group)
    if temporal_period:
        commits = aggregate_daily(commits)

    kwargs: dict[str, Any] = {
        "min_revs": min_revs,
        "min_shared_revs": min_shared_revs,
        "min_coupling": min_coupling,
        "max_coupling": max_coupling,
        "max_changeset_size": max_changeset_size,
        "expression": expression_to_match,
        "age_time_now": date.fromisoformat(age_time_now) if age_time_now else None,
        "verbose": verbose_results,
    }
    fn = ANALYSES[analysis]
    accepted = fn.__code__.co_varnames[: fn.__code__.co_argcount]
    rendered = fn(commits, **{k: v for k, v in kwargs.items() if k in accepted})
    rendered = rendered[:rows] if rows is not None else rendered

    text = to_csv(rendered) if output_format == "csv" else to_json(rendered)
    if output_file:
        output_file.write_text(text, encoding="utf-8")
    else:
        typer.echo(text, nl=False)


@app.command("validate-mapping")
def validate_mapping(
    mapping_file: Path = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-p"),
) -> None:
    result = validate_group_mapping(repo, mapping_file)
    text = to_csv(result)
    typer.echo(text, nl=False)


@app.command("pr-gate")
def pr_gate(
    repo: Path = typer.Option(Path("."), "--repo", "-p"),
    base_ref: str = typer.Option("origin/main", "--base-ref"),
    fail_on_increase: float = typer.Option(0.0, "--fail-on-increase"),
) -> None:
    changed = set(changed_files_against_base(repo, base_ref))
    result = run_pr_gate(repo=repo, base_ref=base_ref, changed=changed)
    typer.echo(to_csv(result), nl=False)
    if result and float(result[0]["delta-score"]) > fail_on_increase:
        raise typer.Exit(code=2)


@app.command("ui")
def launch_ui() -> None:
    from giticizer.ui import run_ui

    run_ui()


@app.command("analyses")
def analyses_help() -> None:
    names = sorted(ANALYSES.keys())
    typer.echo(render_all_analysis_help(names))


@app.command("explain-analysis")
def explain_analysis(
    analysis: str = typer.Option(..., "--analysis", "-a", help="Analysis name to explain."),
) -> None:
    if analysis not in ANALYSES:
        raise typer.BadParameter(f"Unsupported analysis '{analysis}'")
    typer.echo(f"{analysis}\n{render_analysis_help(analysis)}")
