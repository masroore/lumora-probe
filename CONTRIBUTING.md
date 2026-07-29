# Contributing to Lumora Probe

## Scope

Lumora Probe is an engineering platform for DICOM observability and troubleshooting.
Probe Lite and Sender Lite are separate trusted-network command-line tools.

## Development setup

Use CPython 3.13 or newer and `uv`:

```console
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run lint-imports --no-cache
```

## Architecture changes

Treat `docs/planning/`, `docs/adr/`, and `docs/architecture-baseline/` as the
architecture contract. Implement only the approved phase and task. If implementation
requires changing an accepted architectural decision, add a new ADR before changing
code. Do not silently revise an existing ADR.

## Pull requests

- Keep each commit focused on one completed task.
- Include tests and documentation with implementation changes.
- Report known limitations and unverified checks.
- Do not commit patient data or de-identified clinical data. Use generated synthetic
  fixtures only.
- Run all applicable quality gates before requesting review.
