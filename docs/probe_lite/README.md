# Probe Lite (`probe-lite`)

Probe Lite is a small DICOM Storage SCP and Verification SCP for trusted engineering
networks. It accepts C-STORE and C-ECHO associations, writes each received instance to the
filesystem, and emits stdout-only text or JSON Lines events.

> **No security.** Probe Lite provides no authentication or TLS and binds to all local
> interfaces. Use it only on a trusted network, or restrict access outside the process.

## Install and run

Probe Lite is shipped in the `lumora-probe` distribution and requires CPython 3.13+.
From a checkout:

```console
uv sync --locked
uv run probe-lite
```

After a normal installation, use `probe-lite` or `python -m probe_lite`:

```console
python -m pip install .
probe-lite --output ./storage/inbox
# equivalent:
python -m probe_lite --output ./storage/inbox
```

The receiver defaults to TCP port `11112`, called AE title `PROBE_LITE`, and output
directory `storage/inbox`. It creates directories on demand.

A local sender can target the receiver:

```console
uv run sender-lite --input ./storage/outbox --host 127.0.0.1 --port 11112
```

Press **Ctrl+C** (or **Ctrl+Break** on Windows) for a clean shutdown. The receiver stops
accepting associations, waits up to five seconds for active associations, and logs a
shutdown summary.

## Storage layout

Parsed datasets are written as:

```text
<output>/<StudyInstanceUID>/<SeriesInstanceUID>/<SOPInstanceUID>.dcm
```

All three UIDs must be valid DICOM UIDs before they are used as path components. If a
parsed dataset cannot be written but the original request bytes can be recovered, Probe
Lite writes a raw fallback at:

```text
<output>/<SOPInstanceUID>.dcm.raw
```

The raw fallback is retained for investigation and the sender receives status `0xA900`.
Invalid/missing required UIDs return `0xA900`; filesystem failures return `0xA700`; if raw
request bytes cannot be recovered, the receiver returns `0xC000`.

Existing parsed files at the target path are overwritten. Probe Lite has no retention,
rotation, duplicate-detection, or cleanup policy.

## Command-line interface

```text
probe-lite [-h] [-p PORT] [-a AE_TITLE] [-o OUTPUT]
           [--accept-ae ACCEPT_AE] [-f {text,json}] [--max-pdu MAX_PDU]
           [-v] [--version]
```

| Option | Environment variable | Default | Description |
| --- | --- | --- | --- |
| `-p`, `--port` | `PROBE_LITE_PORT` | `11112` | TCP listen port |
| `-a`, `--ae` | `PROBE_LITE_AE` | `PROBE_LITE` | Called AE title |
| `-o`, `--output` | `PROBE_LITE_OUTPUT` | `storage/inbox` | Instance storage directory |
| `--accept-ae` | `PROBE_LITE_ACCEPT_AE` | any | Comma-separated calling AE whitelist |
| `-f`, `--format` | `PROBE_LITE_FORMAT` | `text` | `text` or `json` output |
| `--max-pdu` | `PROBE_LITE_MAX_PDU` | `16382` | Maximum PDU length in bytes |
| `-v`, `--verbose` | `PROBE_LITE_VERBOSE` | `false` | Include negotiation detail |
| `--version` | — | — | Print version and exit |

Precedence is **command line > environment > defaults**. Invalid values terminate before
opening the listen socket with exit code `2`.

Examples:

```console
probe-lite --port 11112 --ae PROBE_LITE --output ./storage/inbox
PROBE_LITE_ACCEPT_AE=CT_SCANNER uv run probe-lite
PROBE_LITE_FORMAT=json uv run probe-lite | tee probe-events.jsonl
```

`--accept-ae` is an optional calling AE whitelist. Without it, any calling AE may request
an association. This is an AE-title filter, not authentication.

## DICOM behavior

- C-ECHO returns `0x0000`.
- C-STORE supports the standard Storage presentation contexts plus Verification and all
  transfer syntaxes exposed by the installed `pynetdicom` version.
- Private and otherwise unknown public Storage SOP Classes are accepted where the peer can
  negotiate them.
- Dataset reception is chunked to bound memory use for large instances.
- Parsed datasets retain the negotiated file metadata when written with `pydicom.dcmwrite`;
  Probe Lite does not transcode objects.
- Multiple associations are served concurrently by pynetdicom. Counters and per-association
  state are protected by a lock.
- The SCP listens on `("", port)`, so the OS exposes it on all interfaces. Bind restriction
  must be enforced by the host, container, or network policy.

C-STORE status mapping:

| Status | Meaning |
| --- | --- |
| `0x0000` | Dataset persisted successfully |
| `0xA700` | Storage or raw-fallback write failed |
| `0xA900` | Required UIDs invalid/missing, or parsed write failed after raw preservation |
| `0xC000` | Request was malformed and raw bytes were unavailable, or raw fallback UID was invalid |

## Logging

All logs go to stdout. No log files are created and Probe Lite does not configure Python's
global `logging` module.

Text mode is one local-time line per event:

```text
14:32:01.123 [INFO] Association accepted: CALLING_AE=CT_SCANNER PEER=192.0.2.10:54321 CONTEXTS=12
```

JSON mode emits one object per line with an ISO-8601 UTC `timestamp`, `level`, `event`, and
event-specific fields:

```json
{"timestamp":"2026-07-31T12:32:01.123Z","level":"INFO","event":"instance_received","study_uid":"1.2.3","series_uid":"1.2.4","sop_instance_uid":"1.2.5","file_path":"storage/inbox/1.2.3/1.2.4/1.2.5.dcm","size_bytes":524288}
```

Normal events include startup, association requested/accepted/rejected/released/aborted,
C-ECHO received, instance received/store failed, and shutdown. `--verbose` adds requested
and accepted presentation-context and extended-negotiation detail.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Receiver stopped normally |
| `1` | Runtime failure, including an unavailable required DICOM dependency or listen failure |
| `2` | Invalid command-line or environment configuration |
| `130` | Reserved for interrupted command-line conventions; the receiver normally handles its first interrupt as a clean stop |

## Development

Probe Lite tests are part of the repository suite:

```console
uv run pytest tests/test_config.py tests/test_logging.py tests/test_storage.py tests/test_receiver.py -q
uv run pytest -m dicom -q
uv run ruff check src/probe_lite src/lumora_lite_common
```

The test suite uses synthetic DICOM data only. Coverage includes configuration precedence,
path safety, raw-byte preservation, C-ECHO/C-STORE round trips, transfer syntaxes,
concurrent associations, calling AE rejection, and clean shutdown.

Source responsibilities:

```text
src/probe_lite/
├── cli.py       argument/env resolution, lifecycle, and exit codes
├── config.py    immutable CLI/environment configuration
├── log.py       ProbeLogger text/JSONL adapter
├── receiver.py  pynetdicom SCP and DIMSE handlers
└── storage.py   UID-safe parsed and raw filesystem writes
```

Probe Lite shares only small, genuinely common helpers with Sender Lite through
[`lumora_lite_common`](../../src/lumora_lite_common/). The shared scope is recorded in
[ADR-0028](../adr/ADR-0028-lite-shared-common-library.md). It is separate from the
`lumora_probe` application package.
