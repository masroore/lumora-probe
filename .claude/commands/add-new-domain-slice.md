---
name: add-new-domain-slice
description: Workflow command scaffold for add-new-domain-slice in lumora-probe.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-new-domain-slice

Use this workflow when working on **add-new-domain-slice** in `lumora-probe`.

## Goal

Adds a new domain slice or package (e.g., analysis, associations, captures, etc.) with API, contracts, domain, repository, and service modules.

## Common Files

- `src/lumora_probe/*/__init__.py`
- `src/lumora_probe/*/api.py`
- `src/lumora_probe/*/contracts.py`
- `src/lumora_probe/*/domain.py`
- `src/lumora_probe/*/repository.py`
- `src/lumora_probe/*/service.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create new directory under src/lumora_probe/<slice>/
- Add __init__.py, api.py, contracts.py, domain.py, repository.py, service.py to the new slice
- Update pyproject.toml if necessary

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.