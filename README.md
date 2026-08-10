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
```

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
