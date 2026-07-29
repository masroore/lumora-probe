---
name: feature-implementation-with-tests-and-docs
description: Workflow command scaffold for feature-implementation-with-tests-and-docs in lumora-probe.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /feature-implementation-with-tests-and-docs

Use this workflow when working on **feature-implementation-with-tests-and-docs** in `lumora-probe`.

## Goal

Implements a new feature or major enhancement, updates or adds related documentation, and adds or updates corresponding tests.

## Common Files

- `src/lumora_probe/*/*.py`
- `tests/test_*.py`
- `docs/**/*.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Implement feature in src/lumora_probe/*/*.py
- Add or update relevant test files in tests/
- Add or update documentation in docs/ or docs/adr/

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.