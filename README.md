# Lumora Probe Lite

Cross-platform CPython command-line DICOM receiver. Probe Lite accepts C-ECHO and
C-STORE associations and writes each received instance to:

```text
<output>/<StudyInstanceUID>/<SeriesInstanceUID>/<SOPInstanceUID>.dcm
```

Supported platforms: **Windows, macOS, and Linux**. Supported runtime: **CPython
3.13 or newer**.

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

## Run

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

## Configuration

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

This is a trusted-network debugging utility. It provides no authentication or TLS.

## Verify locally

Run the same checks used by CI:

```console
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

CI runs these checks on CPython 3.13 for Ubuntu, macOS, and Windows.
