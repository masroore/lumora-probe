# Probe Lite (`probe-lite`)

A minimal **DICOM C-STORE and C-ECHO receiver** (a DICOM *Service Class Provider*, SCP)
for command-line use. It accepts associations from imaging modalities and PACS nodes,
answers C-ECHO verification requests, and writes received C-STORE instances to the
local filesystem in a Study/Series/Instance hierarchy.

> **No security.** Probe Lite performs no authentication or encryption and binds to
> **all network interfaces**. Run it only on trusted, isolated networks.
> (This matches the program's own help text and `ADR-0009` / `ADR-0010`.)

Distribution: `lumora-probe` · Version: `0.1.0` · Requires: **Python ≥ 3.13**

---

## Contents

- [Key features](#key-features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Command-line reference](#command-line-reference)
- [Configuration](#configuration)
- [Storage layout](#storage-layout)
- [Logging](#logging)
- [Exit codes and error behavior](#exit-codes-and-error-behavior)
- [DICOM behavior](#dicom-behavior)
- [Development and testing](#development-and-testing)
- [Project structure](#project-structure)

---

## Key features

- **C-ECHO** verification (DICOM Verification SOP Class).
- **C-STORE** reception of any storage SOP Class, any transfer syntax.
- **Filesystem storage** organized as `<output>/<StudyUID>/<SeriesUID>/<SOPInstanceUID>.dcm`.
- **Raw fallback**: undecodable datasets are preserved verbatim as `<SOPInstanceUID>.dcm.raw`
  so no data is silently lost.
- **Path-traversal-safe UID validation** before any file is written.
- **Optional Calling AE whitelist** (`--accept-ae`) to restrict which senders may associate.
- **Two log formats**: human-readable `text` and machine-parseable JSON Lines (`json`).
- **Concurrent associations** served from a single threaded SCP, with thread-safe counters.
- **Graceful shutdown** on `SIGINT` / `SIGTERM`.

## Requirements

- Python **3.13** or newer (configured in `.python-version`; `target-version = "py313"`).
- Runtime dependencies (declared in `pyproject.toml`):
  - [`pydicom`](https://pydicom.github.io/pydicom) `>=3.0,<4.0`
  - [`pynetdicom`](https://pydicom.github.io/pynetdicom) `>=3.0,<4.0`
- A network path reachable by your DICOM senders (modalities, test SCUs, etc.).

## Installation

Create a virtual environment and install the package (editable is recommended for
local use):

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

This installs the **`probe-lite`** console script (see `[project.scripts]`).

You can also run it directly as a module without installing the script:

```bash
python -m probe_lite [options]
```

## Quick start

Start the receiver on the default port `11112`, storing files under `./received`:

```bash
probe-lite
```

Start on a custom port with JSON logging and a Calling AE whitelist:

```bash
probe-lite -p 104 -o /var/dicom/inbox --accept-ae "CT_SCANNER,WORKSTATION1" -f json
```

Send a test C-ECHO / C-STORE from a peer using any DICOM SCU (e.g. `pynetdicom`'s
`associate` API, or tools like `dcmtk`'s `echoscu` / `storescu`):

```bash
echoscu 127.0.0.1 104 -aec PROBE_LITE
storescu 127.0.0.1 104 image.dcm
```

Stop the server with `Ctrl-C` (`SIGINT`) or `SIGTERM`; it finishes active
associations and exits `0`.

## Command-line reference

```
usage: probe-lite [-h] [-p PORT] [-a AE_TITLE] [-o OUTPUT]
                  [--accept-ae ACCEPT_AE] [-f {text,json}] [--max-pdu MAX_PDU]
                  [-v] [--version]

Minimal DICOM C-STORE and C-ECHO receiver. No security. Use on trusted networks only.

options:
  -h, --help            show this help message and exit
  -p, --port PORT       TCP listen port (env: PROBE_LITE_PORT; default: 11112)
  -a, --ae AE_TITLE     Called AE title (env: PROBE_LITE_AE; default: PROBE_LITE)
  -o, --output OUTPUT   Instance storage directory (env: PROBE_LITE_OUTPUT; default: ./received)
  --accept-ae ACCEPT_AE
                        Comma-separated Calling AE whitelist (env: PROBE_LITE_ACCEPT_AE; default: any)
  -f, --format {text,json}
                        Log format (env: PROBE_LITE_FORMAT; default: text)
  --max-pdu MAX_PDU     Maximum PDU length in bytes (env: PROBE_LITE_MAX_PDU; default: 16382)
  -v, --verbose         Include DICOM negotiation detail (env: PROBE_LITE_VERBOSE; default: false)
  --version             show program's version number and exit
```

`probe-lite --version` prints `probe-lite 0.1.0`.

## Configuration

Configuration is resolved from three sources with **precedence: CLI flags > environment
variables > defaults** (implemented in `src/probe_lite/config.py`).

| Option      | Flag           | Environment variable    | Default     | Validation |
|-------------|----------------|-------------------------|-------------|------------|
| Port        | `-p/--port`    | `PROBE_LITE_PORT`       | `11112`     | Integer `1`–`65535` |
| Called AE   | `-a/--ae`      | `PROBE_LITE_AE`         | `PROBE_LITE`| 1–16 ASCII characters |
| Output dir  | `-o/--output`  | `PROBE_LITE_OUTPUT`     | `./received`| A writable path |
| Calling AE whitelist | `--accept-ae` | `PROBE_LITE_ACCEPT_AE` | *any* | Comma-separated; each 1–16 ASCII chars. Empty/blank ⇒ accept any |
| Log format  | `-f/--format`  | `PROBE_LITE_FORMAT`     | `text`      | One of `text`, `json` |
| Max PDU     | `--max-pdu`    | `PROBE_LITE_MAX_PDU`    | `16382`     | Integer `1`–`16777215` |
| Verbose     | `-v/--verbose` | `PROBE_LITE_VERBOSE`    | `false`     | Boolean: `1/true/yes/on` or `0/false/no/off` |

Notes:

- **`--accept-ae`** is parsed by splitting on commas and trimming whitespace, e.g.
  `"ONE, TWO"` → `{ONE, TWO}`. When set, Probe Lite configures pynetdicom's
  `require_calling_aet`, so associations from any *other* Calling AE are rejected.
- **Verbose** (`-v` / `PROBE_LITE_VERBOSE=true`) additionally emits a
  `association_negotiation` event per association showing requested/accepted
  presentation contexts (abstract + transfer syntaxes) and extended negotiation items.
- Invalid configuration raises `ValueError`, which the CLI reports and exits with
  code `2` (see [Exit codes](#exit-codes-and-error-behavior)).

Example — drive everything from the environment:

```bash
export PROBE_LITE_PORT=104
export PROBE_LITE_OUTPUT=/var/dicom/inbox
export PROBE_LITE_FORMAT=json
export PROBE_LITE_ACCEPT_AE="CT_SCANNER, WORKSTATION1"
probe-lite
```

## Storage layout

Instances are written by `src/probe_lite/storage.py`:

- **Normal datasets** → `<output>/<StudyInstanceUID>/<SeriesInstanceUID>/<SOPInstanceUID>.dcm`
  (written via `pydicom.filewriter.dcmwrite`, file meta preserved).
- **Raw fallback** → `<output>/<SOPInstanceUID>.dcm.raw` (verbatim request bytes).

Example tree after receiving a study:

```
/var/dicom/inbox/
└── 1.2.840...study
    └── 1.2.840...series
        ├── 1.2.840...instance1.dcm
        └── 1.2.840...instance2.dcm
```

**UID safety.** Every path component is validated by `_safe_uid` before use: the value
must match `^[0-9]+(?:\.[0-9]+)+$` and be at most 64 characters long. This rejects
path-traversal attempts (e.g. `../escape`) and malformed UIDs, returning DICOM status
`0xA900` (cannot store). Raw files are keyed solely by SOP Instance UID under the same
validation.

## Logging

`src/probe_lite/log.py` provides a self-contained logger that writes **only to stdout**
(no file handlers, no global `logging` configuration). The format is chosen with
`--format` / `PROBE_LITE_FORMAT`.

**`json`** emits one JSON Lines object per event, for example:

```json
{"timestamp":"2026-07-28T12:00:00.123Z","level":"INFO","event":"instance_received","sop_instance_uid":"1.2.3","size_bytes":2048}
```

- `timestamp` is UTC ISO-8601 with millisecond precision and a trailing `Z`.
- `level` is one of `INFO`, `WARNING`, `ERROR`.

**`text`** (default) emits a single human-readable line per event, for example:

```
12:00:00.123 [INFO] Instance received: SOP_INSTANCE_UID=1.2.3 SIZE_BYTES=2048
```

Emitted events include: `startup`, `association_requested`, `association_accepted`,
`association_rejected`, `association_released`, `association_aborted`,
`association_negotiation` (verbose only), `c_echo_received`, `instance_received`,
`instance_store_failed`, and `shutdown`.

> pynetdicom's own logging is silenced (`LOG_HANDLER_LEVEL = "none"` in
> `receiver.py`) so the only output on stdout is Probe Lite's structured events.

## Exit codes and error behavior

| Code | Meaning | Trigger |
|------|---------|---------|
| `0`  | Clean shutdown | `SIGINT`/`SIGTERM` received and graceful stop completed |
| `1`  | Startup failure | `OSError` (e.g. port already in use) or `RuntimeError` (missing `pynetdicom`/`pydicom`) |
| `2`  | Configuration error | Invalid flag/env value fails validation |

On a bad configuration the CLI prints a single line:

```
probe-lite: configuration error: port must be between 1 and 65535
```

and exits `2` without binding any socket. Original signal handlers are restored in a
`finally` block before the process exits.

## DICOM behavior

`src/probe_lite/receiver.py` builds the pynetdicom `AE` and handles DIMSE events.

- **Supported contexts:** all storage SOP Classes from `AllStoragePresentationContexts`
  **plus** the Verification SOP Class, each negotiated with **all transfer syntaxes**.
- **Unrestricted storage service** is enabled (`UNRESTRICTED_STORAGE_SERVICE = True`) so
  private and unknown public storage SOP Classes are accepted rather than silently refused.
- **Chunked dataset reception** is enabled (`STORE_RECV_CHUNKED_DATASET = True`) to bound
  memory use for large instances.
- **C-ECHO** returns DICOM success `0x0000`.
- **C-STORE** status codes returned to the sender:

  | Status | Constant | When |
  |--------|----------|------|
  | `0x0000` | `SUCCESS` | Instance stored successfully |
  | `0xA700` | `OUT_OF_RESOURCES` | Disk/write failure (`StorageError`) |
  | `0xA900` | `DATASET_DOES_NOT_MATCH_SOP_CLASS` | Missing/invalid UIDs, or dataset unparseable but raw bytes preserved |
  | `0xC000` | `CANNOT_UNDERSTAND` | Malformed request where even raw bytes are unavailable |

- **Raw fallback** (`_fallback_raw`): if decoding/writing the parsed dataset fails,
  the original request bytes are saved as `.dcm.raw` and the sender receives `0xA900`
  with a warning logged; no instance is lost. If the raw bytes themselves cannot be
  obtained, the sender receives `0xC000`.
- **Network binding:** the SCP binds to `("", port)`, i.e. **all interfaces** — another
  reason it is restricted to trusted networks.
- **Concurrency:** counters (`total_instances`, `total_associations`) and per-association
  state are guarded by a `threading.Lock`; multiple associations are served concurrently.

## Development and testing

Dev dependencies (PEP 735 `[dependency-groups] dev` in `pyproject.toml`):
`pytest>=9.0` and `ruff>=0.12`.

Set up a dev environment and run the full suite:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .            # runtime deps (pydicom, pynetdicom)
pip install pytest ruff     # or your group-aware installer for [dependency-groups]

pytest                      # run all tests (testpaths = ["tests"])
pytest -v                   # verbose
pytest tests/test_config.py # a single module
```

Lint / format:

```bash
ruff check .                # lint (line-length = 100, target py313)
ruff format .               # format
```

> The tests use `pytest.importorskip("pydicom")` / `pynetdicom`, so the receiver
> integration tests are skipped automatically if those libraries are not installed.

Tests cover (see `tests/`):

- Defaults, environment values, CLI-over-environment precedence, and rejection of
  invalid values (`test_config.py`).
- JSON Lines vs. single-line text formatting (`test_logging.py`).
- Storage hierarchy, path-traversal rejection, and raw-byte preservation (`test_storage.py`).
- End-to-end C-ECHO/C-STORE round trip, study/series partitioning, transfer-syntax
  preservation (Implicit/Explicit VR Little Endian, Explicit VR Big Endian),
  simultaneous associations, Calling AE rejection, raw fallback, and clean shutdown
  (`test_receiver.py`).

There is no dedicated build/packaging step beyond standard PEP 517; the build backend
is **hatchling** (`[build-system]`). To build a wheel/sdist, use your usual
`python -m build` / `hatch build` / `pip wheel .` flow — nothing project-specific is
required.

### Adding functionality safely

- Configuration changes: extend `Config` and `_validate` in `config.py`; every new
  option needs a CLI flag, an `PROBE_LITE_*` env var, a default, and a validation rule
  to keep precedence consistent.
- New DIMSE/status handling: add handlers in `receiver.py` and a covering test in
  `tests/test_receiver.py`.
- Keep the logger stdout-only and dependency-free; do not introduce global `logging`
  configuration.

## Project structure

```
src/probe_lite/
├── __init__.py     # package marker, __version__ = "0.1.0"
├── __main__.py     # `python -m probe_lite` entry (SystemExit(cli.main()))
├── cli.py          # `probe-lite` console entry: config, logging, signals, exit codes
├── config.py       # argparse + env resolution, Config dataclass, validation
├── log.py          # ProbeLogger (text / JSONL, stdout only)
├── receiver.py     # pynetdicom SCP: AE build, DIMSE handlers, raw fallback, shutdown
└── storage.py      # filesystem persistence, UID validation, raw fallback writes
tests/
├── test_config.py
├── test_logging.py
├── test_receiver.py
└── test_storage.py
pyproject.toml      # metadata, deps, scripts, hatchling build, ruff & pytest config
```

### Module responsibilities

- **`cli.main`** — single entry point. Parses config, constructs `ProbeLogger` +
  `ProbeReceiver`, installs `SIGINT`/`SIGTERM` handlers that set a `threading.Event`,
  then blocks in `receiver.serve(stop_event)`. Maps exceptions to exit codes and
  restores signal handlers in `finally`.
- **`config`** — resolves `Config` (frozen, slotted dataclass) from CLI > env > default
  and validates all values before the receiver starts.
- **`receiver.ProbeReceiver`** — builds the pynetdicom `AE` (storage + Verification,
  all transfer syntaxes, chunked + unrestricted storage), wires DIMSE event handlers,
  binds the socket (`start`), blocks until shutdown is signalled (`serve`), and drains
  active associations within a grace period (`stop`, default 5 s).
- **`storage.Storage`** — maps UIDs to safe filesystem paths, writes parsed datasets via
  `pydicom.dcmwrite`, and writes undecodable bytes as `.dcm.raw`. `StorageError` /
  `InvalidDatasetError` are the two failure modes the receiver maps to DICOM status codes.
- **`log.ProbeLogger`** — dependency-free, stdout-only structured events; no global
  `logging` state.

---

*Note: `docs/architecture-baseline/` and `docs/adr/` describe the broader
**Lumora Probe** product. Probe Lite (`src/probe_lite/`) is the standalone minimal receiver
documented here.*
