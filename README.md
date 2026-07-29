# Lumora Probe Lite

Cross-platform CPython command-line DICOM tools. Two utilities ship in this package:

- **Probe Lite** — a C-STORE/C-ECHO receiver that writes each received instance to disk.
- **Sender Lite** — a one-shot C-STORE/C-ECHO sender for trusted engineering networks.

Supported platforms: **Windows, macOS, and Linux**. Supported runtime: **CPython
3.13 or newer**. Both tools are trusted-network debugging utilities and provide no
authentication or TLS.

## Install

Create a virtual environment with the Python launcher for your platform, then install
from this repository:

```console
python -m pip install .
```

For development and tests:

```console
python -m pip install . pytest ruff
```

The package has no platform-specific runtime dependencies or shell requirements.

## Probe Lite

Probe Lite accepts C-ECHO and C-STORE associations and writes each received instance to:

```text
<output>/<StudyInstanceUID>/<SeriesInstanceUID>/<SOPInstanceUID>.dcm
```

### Run

Start the receiver with the default port (`11112`) and output directory (`./received`):

```console
probe-lite
```

Equivalent module invocation works on every supported platform:

```console
python -m probe_lite
```

Use an explicit output path when needed. `pathlib` handles native separators on all
supported platforms:

```console
probe-lite --output ./received --port 11112
```

On Windows, `probe-lite.exe` is installed in the virtual environment's `Scripts` folder;
on macOS and Linux, the executable is in `bin`. Activating the environment or invoking
`python -m probe_lite` avoids PATH differences.

Press **Ctrl+C** (or **Ctrl+Break** on Windows) to request a clean shutdown. Logs are
written to stdout. Use
`--format json` for JSON Lines output.

### Configuration

Command-line arguments override environment variables, which override defaults:

| Argument | Environment variable | Default |
| --- | --- | --- |
| `--port` / `-p` | `PROBE_LITE_PORT` | `11112` |
| `--ae` / `-a` | `PROBE_LITE_AE` | `PROBE_LITE` |
| `--output` / `-o` | `PROBE_LITE_OUTPUT` | `./received` |
| `--accept-ae` | `PROBE_LITE_ACCEPT_AE` | any calling AE |
| `--format` / `-f` | `PROBE_LITE_FORMAT` | `text` |
| `--max-pdu` | `PROBE_LITE_MAX_PDU` | `16382` |
| `--verbose` / `-v` | `PROBE_LITE_VERBOSE` | `false` |

## Sender Lite

Sender Lite is a one-shot sender. It scans an input directory, builds an in-memory
catalog grouped by Study, and sends each Study Batch over exactly one DICOM association,
waiting a configurable delay between Studies. Malformed, inconsistent, or duplicate
files are rejected without stopping the scan.

### Run

Send every DICOM instance found under an input directory:

```console
sender-lite --input ./dicom
```

Equivalent module invocation works on every supported platform:

```console
python -m sender_lite
```

Target an explicit peer and AE titles:

```console
sender-lite --input ./dicom --host 127.0.0.1 --port 11112 \
    --calling-ae SENDER_LITE --called-ae PROBE_LITE
```

Run a connectivity check with C-ECHO instead of sending:

```console
sender-lite --echo --host 127.0.0.1 --port 11112
```

On Windows, `sender-lite.exe` is installed in the virtual environment's `Scripts`
folder; on macOS and Linux, the executable is in `bin`.

Press **Ctrl+C** (or **Ctrl+Break** on Windows) to request cancellation. The first
signal stops cleanly after the current operation; a second signal terminates
immediately. Logs are written to stdout. Use `--format json` for JSON Lines output.

### Configuration

Command-line arguments override a TOML config file, which overrides defaults. With no
arguments, Sender Lite loads `./sender-lite.toml` if present and errors otherwise; use
`--config PATH` to point at another file.

| Argument | TOML key | Default |
| --- | --- | --- |
| `--input` | `input` | *(required)* |
| `--host` | `host` | `127.0.0.1` |
| `--port` / `-p` | `port` | `11112` |
| `--calling-ae` | `calling_ae` | `SENDER_LITE` |
| `--called-ae` | `called_ae` | `PROBE_LITE` |
| `--study-delay` | `study_delay` | `1.0` |
| `--connect-timeout` | `connect_timeout` | `10.0` |
| `--dimse-timeout` | `dimse_timeout` | `30.0` |
| `--max-pdu` | `max_pdu` | `16382` |
| `--format` / `-f` | `log_format` | `text` |
| `--echo` | — | `false` |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | all attempted Instances succeeded or warned; or Echo succeeded |
| `1` | any Instance/Study failed, empty Catalog, Echo failure, or runtime error |
| `2` | invalid CLI/TOML configuration or usage |
| `130` | interrupted/cancelled before completion |

## Shared library

Both tools share a small internal package, `lumora_lite_common`, which holds the
genuinely duplicated helpers: the event-logger engine (an `EventLogger` base class that
`ProbeLogger` and `SenderLogger` extend), portable signal install/restore, config leaf
validators (port, max PDU, log format, AE title), and DICOM UID validation. See
ADR-0028 for the scope and the pragmatic-OOP boundary. This is internal to the Lite
tools and does not share code with the parent `lumora/` project.

## Verify locally

```console
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

CI runs these checks on CPython 3.13 for Ubuntu, macOS, and Windows.
