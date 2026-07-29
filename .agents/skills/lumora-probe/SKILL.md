```markdown
# lumora-probe Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you how to contribute effectively to the `lumora-probe` Python codebase. You'll learn the repository's coding conventions, modular architecture, and the main workflows for adding features, domains, infrastructure, tests, and quality improvements. This guide covers file organization, commit patterns, and practical step-by-step instructions for common development tasks.

## Coding Conventions

- **Language:** Python (no framework detected)
- **File Naming:** Use `snake_case` for all files and directories.
  - Example: `capture_service.py`, `event_catalog.py`
- **Imports:** Use relative imports within packages.
  - Example:
    ```python
    from .domain import CaptureDomain
    from .repository import CaptureRepository
    ```
- **Exports:** Use named exports (explicitly define what is exported in `__init__.py`).
  - Example (`__init__.py`):
    ```python
    from .api import CaptureAPI
    from .service import CaptureService

    __all__ = ["CaptureAPI", "CaptureService"]
    ```
- **Commit Messages:** Follow [Conventional Commits](https://www.conventionalcommits.org/), using prefixes like `feat`, `fix`, `docs`, `test`, `chore`, `ci`.
  - Example: `feat(analysis): add support for new metric calculation`

## Workflows

### Add New Domain Slice

**Trigger:** When introducing a new logical domain or feature area  
**Command:** `/new-domain-slice`

1. Create a new directory under `src/lumora_probe/<slice>/`
2. Add the following files to the new slice:
    - `__init__.py`
    - `api.py`
    - `contracts.py`
    - `domain.py`
    - `repository.py`
    - `service.py`
3. Update `pyproject.toml` if necessary to register the new package.

**Example:**
```bash
mkdir src/lumora_probe/associations
touch src/lumora_probe/associations/{__init__.py,api.py,contracts.py,domain.py,repository.py,service.py}
```

---

### Feature Implementation with Tests and Docs

**Trigger:** When adding a new feature or major enhancement  
**Command:** `/feature`

1. Implement the feature in the relevant `src/lumora_probe/*/*.py` files.
2. Add or update tests in `tests/` (e.g., `tests/test_feature.py`).
3. Add or update documentation in `docs/` or `docs/adr/`.

**Example:**
```python
# src/lumora_probe/analysis/service.py
def calculate_metric(data):
    # implementation
    pass
```
```python
# tests/test_analysis.py
def test_calculate_metric():
    assert calculate_metric([1, 2, 3]) == expected_value
```

---

### Add or Update Generated Catalog or OpenAPI

**Trigger:** When updating the event catalog or OpenAPI schema after API/event changes  
**Command:** `/generate-catalog`

1. Generate new catalog or OpenAPI JSON in `docs/generated/`.
2. Update or add the generator script in `scripts/`.
3. Add or update related tests in `tests/`.

**Example:**
```bash
python scripts/generate_openapi.py
```

---

### Add or Update Core Infrastructure Component

**Trigger:** When adding or modifying a core infrastructure component (storage, event bus, config, logging)  
**Command:** `/infra`

1. Implement or modify the component in `src/lumora_probe/core/*.py`.
2. Add or update tests in `tests/`.

---

### Add or Update Test Fixtures and Harnesses

**Trigger:** When introducing new test data or fixture generation utilities  
**Command:** `/add-fixture`

1. Add or update fixture generator scripts in `scripts/`.
2. Add or update fixture data in `tests/fixtures/` and `tests/golden/`.
3. Add or update test harnesses in `tests/`.

**Example:**
```bash
python scripts/generate_sample_fixture.py
```

---

### Update Repository Quality or CI Tooling

**Trigger:** When enforcing or improving code quality or CI pipelines  
**Command:** `/quality`

1. Update `pyproject.toml` or other config files.
2. Update `.github/workflows/*.yml` for CI changes.
3. Update or add linting/formatting configs (e.g., `.importlinter`).
4. Update tests if necessary.

---

## Testing Patterns

- **Test Files:** Located in `tests/`, named as `test_*.py`.
- **Testing Framework:** Not explicitly detected; likely uses `pytest` or standard Python `unittest`.
- **Test Structure:** Place tests alongside fixtures and golden data when needed.
- **Example Test:**
    ```python
    # tests/test_capture.py
    def test_capture_creation():
        capture = CaptureDomain("example")
        assert capture.name == "example"
    ```

## Commands

| Command             | Purpose                                                      |
|---------------------|--------------------------------------------------------------|
| /new-domain-slice   | Scaffold a new domain slice with standard module files       |
| /feature            | Add a new feature with tests and documentation               |
| /generate-catalog   | Generate or update event/OpenAPI catalogs and related tests  |
| /infra              | Add or update a core infrastructure component                |
| /add-fixture        | Add or update test fixtures, harnesses, or sample data       |
| /quality            | Update repository-wide quality tooling or CI configuration   |
```
