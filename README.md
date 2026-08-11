# Giticizer

Giticizer is a Python CLI for behavioral code analysis inspired by Code Maat.

## Tooling

- Dependency management: `uv`
- CLI: `typer`
- Linting: `ruff`
- Type checking: `ty`

## Quick start

```bash
uv sync
uv run giticizer analyze --repo . --analysis summary --output-format csv
uv run giticizer analyze --repo . --analysis coupling --include-dir src/backend --output-format csv
```

Note: `--include-dir` must point to a directory inside the selected `--repo`.

## Desktop UI

Launch the local UI and select any Git repository folder from the picker.

```bash
uv run giticizer ui
```

In the UI you can:

- choose the repository folder
- choose any available analysis
- filter scope with Include Dirs (comma-separated paths inside repo)
- adjust thresholds and options
- run and inspect results in a table
- inspect daily refactoring cards in the second tab

## Implemented analyses

- `summary`
- `authors`
- `coupling`
- `age`
- `abs-churn`
- `author-churn`
- `entity-churn`
- `entity-ownership`
- `entity-effort`
- `main-dev`
- `main-dev-by-revs`
- `revisions`
- `messages`
- `identity`
- `communication`
- `fragmentation`
- `soc`
- `refactoring-main-dev`
- `code-health`
- `action-items`
