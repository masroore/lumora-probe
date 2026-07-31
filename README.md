# Lumora Probe

Lumora Probe is an engineering observability platform for DICOM network traffic: capture,
replay, analyze, and troubleshoot — **browser devtools for DICOM**.

The repository also ships two standalone Lite command-line utilities for small, trusted
network tests:

- **Probe Lite** — C-STORE/C-ECHO receiver that writes received instances to disk.
- **Sender Lite** — one-shot C-STORE/C-ECHO sender that catalogs a directory and sends one
  Study Batch per DICOM association.

Release `0.1.0` reached GA sign-off on **July 31, 2026** for trusted engineering
deployments. The release is not a clinical workstation, PACS archive, RIS/EMR, reporting
system, or AI diagnostic platform. See [known limitations](docs/guides/known-limitations.md).

## Quick start: Lumora Probe

Requirements: CPython 3.13+, `uv`, and a supported Unix-like or Windows environment.
Node is not required to install or run the application; committed frontend assets are
included in the wheel and container image.

```console
uv sync --locked
uv run lumora serve
```

The server binds HTTP to `127.0.0.1:8000` and the DICOM listener to
`127.0.0.1:11112` by default. Open the local UI at `http://127.0.0.1:8000/` or use the
CLI/API against that server:

```console
uv run lumora health
uv run lumora captures list
uv run lumora capture inspect path/to/capture.lpcap
```

The default data directory is platform-specific:

- Linux: `$XDG_DATA_HOME/lumora-probe`, or `~/.local/share/lumora-probe`.
- macOS: `~/Library/Application Support/Lumora Probe`.
- Windows: `%APPDATA%\\Lumora Probe`.

Set `LUMORA_DATA_DIR` to choose another root. Startup configuration precedence is
**environment > `.env` > `lumora.toml`/`lumora.yaml` > defaults**. Non-loopback HTTP or
DICOM binds require an explicit trust acknowledgment:

```console
uv run lumora serve --trust-network --host 0.0.0.0
```

Lumora Probe provides no authentication, RBAC, or in-process TLS in v1. Put a reverse
proxy or another trusted network boundary in front of any non-loopback deployment.

## Quick start: Lite utilities

Both utilities are included in the same distribution and require only CPython plus the
project dependencies:

```console
uv run probe-lite
uv run sender-lite --echo
```

For a local receiver/sender round trip:

```console
uv run probe-lite --output ./storage/inbox
uv run sender-lite --input ./storage/outbox --host 127.0.0.1 --port 11112
```

Lite utilities bind or connect without authentication or TLS. Use them only on a trusted
engineering network. Full command, configuration, storage, catalog, logging, and exit-code
contracts:

- [Probe Lite guide](docs/probe_lite/README.md)
- [Sender Lite guide](docs/sender_lite/README.md)
- [Lite vocabulary](CONTEXT.md)
- [Lite shared-library decision](docs/adr/ADR-0028-lite-shared-common-library.md)
- [Neutral DICOM infrastructure decision](docs/adr/ADR-0034-neutral-dicom-common-infrastructure.md)

## Install from a built distribution

For an editable development install:

```console
uv sync --locked
```

For a normal wheel/sdist install:

```console
python -m pip install .
```

The package metadata exposes these console entry points:

| Command | Purpose |
| --- | --- |
| `lumora` | Lumora Probe server and live/offline CLI |
| `probe-lite` | Minimal DICOM receiver |
| `sender-lite` | One-shot DICOM sender |

Python module invocation is available for both Lite utilities:
`python -m probe_lite` and `python -m sender_lite`.

## Development

All locked Python commands run through `uv`:

```console
uv run pytest -q
uv run pytest -m unit -q
uv run ruff check .
uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared
```

Interop tests are opt-in:

```console
LUMORA_INTEROP=1 uv run pytest -m interop
# Start the external peers first when required:
# docker compose -f tests/interop/docker-compose.yml --profile interop up -d
```

Frontend assets are committed and CI checks for drift. Rebuild them only when changing
asset sources:

```console
npm ci
npm run build:assets
npm run check:assets
```

Synthetic DICOM fixtures are generated with `scripts/generate_fixtures.py`. Never add real
or de-identified patient data to the repository.

## Repository layout

```text
src/
├── lumora_probe/        Lumora Probe application, module-first slices
├── probe_lite/          Probe Lite receiver
├── sender_lite/         Sender Lite sender
├── lumora_lite_common/  Lite-only logger, signals, validators, and UID facade
└── lumora_dicom_common/  Neutral DICOM mechanics (ADR-0034)

docs/
├── adr/                 Authoritative architecture decisions
├── architecture-baseline/  Product and architecture baseline
├── generated/           OpenAPI, AsyncAPI, event, and condition artifacts
├── guides/              Operator, deployment, privacy, troubleshooting, and handover guides
├── probe_lite/          Probe Lite documentation
├── sender_lite/         Sender Lite documentation
└── planning/            Historical plans, completion reports, and release evidence
```

Start at [the documentation index](docs/README.md). Architecture decisions in `docs/adr/`
precede the architecture baseline and planning documents when they conflict.

## Architecture and security posture

Lumora Probe is a single-process application with an asyncio event bus, threaded
pynetdicom boundary, SQLite Core storage, and server-side DICOM decoding. Captures are
authoritative evidence; the derived index is rebuildable. Plugins are trusted in-process
code, not sandboxed extensions.

Important v1 boundaries:

- No authentication, RBAC, or TLS termination.
- Non-loopback exposure is denied unless explicitly acknowledged.
- C-MOVE sub-operations, PCAP import, remote collectors, byte-exact mock-peer replay,
  Prometheus exposition, and PS3.15 de-identification remain deferred.
- The application is for engineering observability, not clinical use.

See [operator guide](docs/guides/operator-guide.md),
[deployment topologies](docs/guides/deployment-topologies.md),
[privacy posture](docs/guides/privacy-and-compliance-posture.md), and
[known limitations](docs/guides/known-limitations.md).

## License

See [LICENSE](LICENSE).
