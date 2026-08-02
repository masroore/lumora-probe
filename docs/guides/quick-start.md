# Quick Start

Get a Lumora Probe server running, capture your first DICOM association, and try the Lite
utilities — all in about ten minutes.

## Prerequisites

- CPython **3.13+**
- `uv` (fast Python package manager; see [astral.sh/uv](https://docs.astral.sh/uv/))
- A Unix-like environment or Windows

Node is **not** required: committed frontend assets are included in the wheel and container
image.

## 1. Install and start the server

```console
uv sync --locked
uv run lumora serve
```

The server binds HTTP to `127.0.0.1:8000` and the DICOM listener to `127.0.0.1:11112` by
default. Open the UI at <http://127.0.0.1:8000/>.

Verify the server is healthy in a second terminal:

```console
uv run lumora health
uv run lumora captures list
```

## 2. Capture your first DICOM traffic

Lumora Probe observes C-STORE and C-ECHO associations sent to its DICOM listener. The
easiest way to generate traffic is with the bundled Lite utilities — see
[step 4](#4-try-the-lite-utilities). Point any DICOM SCU (an integration under test, a
fixture script) at `127.0.0.1:11112` and the capture engine records it.

Inspect a capture offline without the server running:

```console
uv run lumora capture inspect path/to/capture.lpcap
```

## 3. Try the Lite utilities

Both utilities ship in the same distribution. Start a receiver, then send a synthetic study:

```console
uv run probe-lite --output ./storage/inbox
```

In a second terminal:

```console
uv run sender-lite --input ./storage/outbox --host 127.0.0.1 --port 11112
```

`sender-lite` catalogs the directory, groups instances into **Study Batches** by Study, and
sends each batch over one association. For a pure connectivity check without sending
anything:

```console
uv run sender-lite --echo --host 127.0.0.1 --port 11112
```

Both tools are for **trusted engineering networks only** — no authentication or TLS.

## 4. Generate synthetic DICOM data

Never copy real or de-identified patient data into the repo. Use the fixture generator:

```console
uv run python scripts/generate_fixtures.py ./storage/outbox
```

This writes a deterministic synthetic study (2 series, 3 instances) under the project UID
namespace.

## 5. Common workflows

- **Observe a failing integration**: run Lumora Probe, point the peer's AE at
  `127.0.0.1:11112`, then inspect the event stream in the UI.
- **Investigate a capture**: `uv run lumora capture inspect <capture.lpcap>` or use the
  Study Browser / Timeline in the UI.
- **Export evidence**: use the handover workflow with object-dropping (`events` fidelity)
  unless a controlled redaction flow is required — see
  [vendor handover](vendor-handover.md).

## Data directory

The default data root is platform-specific:

- Linux: `$XDG_DATA_HOME/lumora-probe`, or `~/.local/share/lumora-probe`
- macOS: `~/Library/Application Support/Lumora Probe`
- Windows: `%APPDATA%\Lumora Probe`

Set `LUMORA_DATA_DIR` to choose another root. Everything — `index.db` (rebuildable),
`app.db` (authoritative, back it up), `captures/`, `ringbuffer/`, and settings — derives
from it. See the [operator guide](operator-guide.md) for the layout and backup checklist.

## Container

A non-root single-volume image is available:

```console
docker compose up -d
```

This exposes HTTP on `127.0.0.1:8000` and DICOM on `127.0.0.1:11112` and keeps the full data
tree in the `lumora-data` volume. The image acknowledges non-loopback exposure
(`--trust-network --host 0.0.0.0`) and runs unauthenticated — put a reverse proxy in front
when it leaves a trusted local Docker network. See [Docker deployment](docker.md).

## Security note

Lumora Probe provides **no authentication, RBAC, or in-process TLS** in v1. Non-loopback
HTTP or DICOM binds require an explicit acknowledgment:

```console
uv run lumora serve --trust-network --host 0.0.0.0
```

Prefer loopback binds or a reverse proxy; never expose the server to an untrusted network.
See [known limitations](known-limitations.md) and
[privacy and compliance posture](privacy-and-compliance-posture.md).
