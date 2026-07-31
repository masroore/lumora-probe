# Dependency Review

## 1. Runtime Dependencies

| Package | Pinned range | Assessment |
|---|---|---|
| `pydicom>=3.0,<4.0` | Major-pinned | Correct. pydicom 3.x is the current stable line. |
| `pynetdicom>=3.0,<4.0` | Major-pinned | Correct. pynetdicom 3.x is the current stable line. |
| `pydantic-settings>=2.10,<3.0` | Minor-floor, major-pinned | Acceptable. |
| `structlog>=25.4,<26.0` | Minor-floor, major-pinned | Acceptable. |
| `fastapi>=0.116,<1.0` | Minor-floor, pre-1.0 upper | Acceptable. FastAPI 1.0 will be a semver break. |
| `uvicorn>=0.35,<1.0` | Minor-floor, pre-1.0 upper | Acceptable. |
| `jinja2>=3.1,<4.0` | Minor-floor, major-pinned | Correct. |
| `pluggy>=1.6,<2.0` | Minor-floor, major-pinned | Correct. pluggy is stable. |
| `websockets>=14,<16` | Two-major range | Slightly wide; websockets 15 introduced breaking
 changes. Consider `>=14,<15`. |
| `pylibjpeg>=2.0,<3.0` | Major-pinned | Correct. |
| `pylibjpeg-openjpeg>=2.4,<3.0` | Minor-floor, major-pinned | Correct. |

**Missing runtime dependency:** The custom YAML parser in `core/config.py` calls
`import tomllib` inside a function. `tomllib` is stdlib in Python 3.11+. Since
`requires-python = ">=3.13"`, this is correct and no extra dependency is needed.

**Implicit dependency:** `orjson` is listed in `CLAUDE.md` as part of the toolchain but is
**absent from `pyproject.toml`**. If any module uses `orjson` for JSON serialization, it would
fail at runtime in a fresh install. Review showed that `EventEnvelope.to_json_bytes()` uses
Pydantic's `model_dump_json()`, not `orjson` directly. The `CLAUDE.md` reference to `orjson`
may be aspirational or refer to a planned optimization. No actual `import orjson` was found in
the source files reviewed. This should be clarified.

**`pluggy`:** Plugin system uses `pluggy`. This is the pytest plugin infrastructure. It is a
reasonable choice for hook management in trusted in-process plugins, consistent with ADR-0021
which acknowledges that plugin sandboxing is impossible in-process.

---

## 2. Development Dependencies

| Package | Version constraint | Assessment |
|---|---|---|
| `basedpyright>=1.30,<2.0` | Acceptable | BasedPyright is a strict Pyright fork. |
| `httpx>=0.28,<1.0` | Acceptable | Used for TestClient in FastAPI tests. |
| `import-linter>=2.0,<3.0` | Acceptable | Boundary enforcement tool. |
| `pip-audit>=2.9,<3.0` | Acceptable | Security vulnerability scanning. |
| `pytest>=9.0` | Open upper — missing `<10.0` | Low risk; pytest is stable, but a major version
 bump could break test configuration. |
| `pytest-asyncio>=1.0,<2.0` | Acceptable | |
| `pytest-cov>=7.0,<8.0` | Acceptable | |
| `pytest-playwright>=0.8.0` | Open upper | playwright is used for a11y/e2e tests. |
| `ruff>=0.12` | Open upper | Ruff has rapid release cycles; an upper bound would prevent
 unexpected linting rule changes. |

**Recommendation:** Add `<10.0` to `pytest` and `<1.0` to `ruff` to prevent surprise breakage
from future major releases.

---

## 3. Build System

`hatchling` is used as the build backend. The wheel configuration explicitly includes
`static/**` and `assets/vendor/**`. Built assets (`static/css/app.css`, Cornerstone bundle)
are committed and shipped in sdist — this is documented in ADR-0025. CI rebuilds and fails on
drift. This is a pragmatic trade-off that avoids Node at install time.

**Concern:** The sdist explicitly includes `uv.lock` in the sdist `include` list. A lock file
in an sdist is unusual and could confuse tools that unpack the sdist for building. The lock file
is appropriate for the development workflow but should not be required for building a wheel from
the sdist.

---

## 4. Package Layout

```toml
packages = [
    "src/lumora_probe",
    "src/probe_lite",
    "src/sender_lite",
    "src/lumora_lite_common",
]
```

The wheel includes four packages. Three of these (`probe_lite`, `sender_lite`,
`lumora_lite_common`) are not reviewed here but are present in the repository. The project
entry points expose three CLI commands:

```toml
[project.scripts]
probe-lite = "probe_lite.cli:main"
sender-lite = "sender_lite.cli:main"
lumora = "lumora_probe.cli:main"
```

This means three different products are shipped in a single wheel. This simplifies distribution
but means a user who only wants `lumora` still installs `probe_lite` and `sender_lite`. At
v0.1.0 this is acceptable; it should be revisited if the packages diverge in dependency
requirements.

---

## 5. Static Type Checking

`basedpyright` is configured with `typeCheckingMode = "strict"` but only for `core/` and
`shared/`:

```toml
[tool.basedpyright]
include = ["src/lumora_probe/core", "src/lumora_probe/shared"]
typeCheckingMode = "strict"
```

The remaining slices (`captures/`, `associations/`, `analysis/`, `replay/`, `reports/`,
`plugins/`, `settings/`, `web/`) are not type-checked. For a system where correctness is the
primary engineering concern, this is a significant gap. Type errors in the capture pipeline,
the association network handler, and the replay service will not be caught statically.

**Recommendation:** Extend `basedpyright` coverage to at least `captures/`, `associations/`,
and `replay/`. The annotation quality in these modules (from what was read) appears sufficient
to support strict checking.

---

## 6. Coupling Analysis

**Tight couplings identified:**

1. `MetricRegistry` imports `shared/events.py` (for `EventEnvelope` type in `observe()`). This
   creates a dependency from `core/` to `shared/`. Per the stated boundary, `core` must not
   import slices, and `shared` imports only `core`. `shared` is not technically a "slice", so
   the import is boundary-compliant, but it creates a dependency cycle if `shared` ever needs
   to import from `core/metrics.py`.

2. `bootstrap.py` imports from 14 different modules. This is appropriate for a composition root
   but means `bootstrap.py` has the highest coupling fanout in the system. Any refactoring of
   the composition root must be done carefully.

3. `CaptureEngine` directly calls `from .format import CapturePackage` inside
   `_index_if_configured()`. This deferred import avoids a circular dependency at module load
   time but obscures the dependency in the class definition. It should be a top-level import.

**Low coupling across domain:**

The domain aggregates (`Capture`, `Association`) are framework-free plain Python with no
dependencies on FastAPI, SQLAlchemy, pydantic, or the bus. This is the correct design and
supports testability.
