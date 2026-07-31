# Sender Lite (`sender-lite`)

Sender Lite is a one-shot DICOM C-STORE/C-ECHO SCU for trusted engineering networks. It
scans an input directory, builds an in-memory **Catalog**, groups sendable instances into
**Study Batches**, sends each Study Batch over one DICOM association, and exits.

> **No security.** Sender Lite provides no authentication or TLS. Use it only on a trusted
> network, or place it behind controls provided by the surrounding environment.

## Install and run

Sender Lite is shipped in the `lumora-probe` distribution and requires CPython 3.13+.
From a checkout:

```console
uv sync --locked
```

Send the default input directory (`storage/outbox`) to the default local Probe Lite peer:

```console
uv run sender-lite --input ./storage/outbox
```

After a normal installation, use `sender-lite` or `python -m sender_lite`:

```console
python -m pip install .
sender-lite --input ./dicom
python -m sender_lite --input ./dicom
```

Run a connectivity check without scanning or sending instances:

```console
uv run sender-lite --echo --host 127.0.0.1 --port 11112
```

A zero-argument invocation requires `sender-lite.toml` in the current directory. Otherwise
provide `--input` or use `--echo`.

## Sending model

1. Recursively scan the input directory for regular files.
2. Read DICOM metadata needed for C-STORE without loading every pixel payload into memory.
3. Reject malformed files, missing/invalid required UIDs, inconsistent metadata, symlinked
   input roots, and duplicate SOP Instance UID conflicts without stopping the scan.
4. Group accepted instances by Study Instance UID, then Series Instance UID.
5. Sort studies, series, and instances deterministically.
6. Open exactly one association per Study Batch, request one presentation context for each
   unique `(SOP Class UID, Transfer Syntax UID)` pair, and send instances sequentially.
7. Wait `study_delay` seconds before the next Study Batch unless cancelled.

Sender Lite does not transcode datasets. If a peer rejects a required presentation context,
the affected instances fail rather than silently changing transfer syntax. A Study Batch that
requires more than 128 presentation contexts fails preflight and is not split across multiple
associations.

The sender revalidates files before transmission. Changes made after cataloging are reported
as failures instead of sending stale assumptions.

## Command-line interface

```text
sender-lite [-h] [--config CONFIG] [-i INPUT] [--host HOST] [-p PORT]
            [--calling-ae CALLING_AE] [--called-ae CALLED_AE]
            [--study-delay STUDY_DELAY] [--connect-timeout CONNECT_TIMEOUT]
            [--dimse-timeout DIMSE_TIMEOUT] [--max-pdu MAX_PDU]
            [-f {text,json}] [-v] [--no-verbose] [--echo] [--version]
```

| Option | Default | Description |
| --- | --- | --- |
| `--config` | — | TOML configuration path |
| `-i`, `--input` | `storage/outbox` | Input DICOM directory; not needed for `--echo` |
| `--host` | `127.0.0.1` | Remote hostname or IP address |
| `-p`, `--port` | `11112` | Remote TCP port |
| `--calling-ae` | `SENDER_LITE` | Calling AE title |
| `--called-ae` | `PROBE_LITE` | Called AE title |
| `--study-delay` | `1.0` | Seconds between Study Batches; zero disables the delay |
| `--connect-timeout` | `10.0` | Association establishment timeout in seconds |
| `--dimse-timeout` | `30.0` | DIMSE/network response timeout in seconds |
| `--max-pdu` | `16382` | Maximum PDU length in bytes |
| `-f`, `--format` | `text` | `text` or `json` output |
| `-v`, `--verbose` | `false` | Include negotiation detail |
| `--no-verbose` | — | Explicitly disable verbose output |
| `--echo` | `false` | Perform C-ECHO only |
| `--version` | — | Print version and exit |

Precedence is **command line > TOML > defaults**. Unknown TOML keys, wrong TOML value
shapes, invalid AE titles/ports/timeouts, missing directories, and symlinked input roots
are configuration errors and terminate with exit code `2`.

## TOML configuration

The default file name is `sender-lite.toml` in the current directory. Use `--config PATH`
to select another file. Only these keys are accepted:

```toml
input = "./storage/outbox"
host = "127.0.0.1"
port = 11112
calling_ae = "SENDER_LITE"
called_ae = "PROBE_LITE"
study_delay = 1.0
connect_timeout = 10.0
dimse_timeout = 30.0
max_pdu = 16382
log_format = "text"
verbose = false
```

CLI options override values from this file. `--echo` is CLI-only and does not require an
input directory.

## Logging

All logs go to stdout. No log files are created. Text mode uses local time and JSON mode
emits one object per line with an ISO-8601 UTC `timestamp`, `level`, `event`, and fields.

Typical events include:

- `scan_started`, `file_skipped`, and `catalog_conflict`;
- `scan_completed` with scanned, rejected, studies, series, instances, and byte totals;
- `study_started`, `association_accepted`/`association_rejected`, and per-instance results;
- `study_delay_started`, `study_completed`, `echo_completed`, `run_failed`, and
  `run_completed`.

Use `--format json` for machine processing:

```console
uv run sender-lite --input ./dicom --format json > sender-events.jsonl
```

`--verbose` includes presentation-context negotiation details. The logger is stdout-only
and does not configure global Python logging state.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | C-ECHO succeeded, or every attempted instance completed without a failed result |
| `1` | Catalog error, empty Catalog, C-ECHO failure, association/runtime failure, or any failed instance |
| `2` | Invalid CLI/TOML configuration or usage |
| `130` | Cancellation/interruption before completion |

A Catalog may contain rejected files while still sending valid files. Rejected files are
reported, but do not by themselves force exit code `1` if at least one sendable instance
completes successfully and no send operation fails. An empty Catalog always returns `1`.

## Cancellation and failure handling

The first interrupt requests cooperative cancellation. Sender Lite finishes the current
safe operation where possible, does not begin the next Study Batch, and returns `130`.
A second interrupt follows the host process's normal force-termination behavior.

A failed Study Batch does not silently retry or move to another association for that same
batch. The final summary reports attempted, succeeded, warned, failed, cancelled, duration,
and exit code.

## Development

Sender Lite tests are part of the repository suite:

```console
uv run pytest tests/test_sender_config.py tests/test_sender_catalog.py tests/test_sender_transport.py tests/test_sender_cli.py -q
uv run pytest -m dicom -q
uv run ruff check src/sender_lite src/lumora_lite_common
```

The test data is synthetic. Coverage includes TOML precedence and validation, recursive
cataloging, deterministic grouping, duplicate conflicts, C-ECHO, per-Study associations,
transfer-syntax preservation, rejected contexts, cancellation, partial failures, and exit
codes.

Source responsibilities:

```text
src/sender_lite/
├── cli.py       argument/config resolution, run lifecycle, logging, and exit codes
├── config.py    CLI/TOML configuration and validation
├── catalog.py   metadata scan, validation, conflict handling, and deterministic grouping
├── log.py       SenderLogger text/JSONL adapter
└── sender.py    C-ECHO, Study associations, C-STORE, cancellation, and result accounting
```

Sender Lite shares only small, genuinely common helpers with Probe Lite through
[`lumora_lite_common`](../../src/lumora_lite_common/). Both Lite tools and the application
may use the separate, neutral [`lumora_dicom_common`](../../src/lumora_dicom_common/)
mechanics package; it contains no product workflow. The Lite-only scope is recorded in
[ADR-0028](../adr/ADR-0028-lite-shared-common-library.md), and the neutral exception in
[ADR-0034](../adr/ADR-0034-neutral-dicom-common-infrastructure.md).
