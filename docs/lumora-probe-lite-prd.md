# Lumora Probe Lite — Product Requirements Document

> **Project:** Lumora Probe Lite
>
> **Document:** Product Requirements Document (PRD)
>
> **Status:** Draft v0.1
>
> **Audience:** Engineering, QA, Claude Code, Codex
>
> **Parent:** Lumora Probe (`docs/architecture-baseline/`)

---

# 1. Introduction

## 1.1 Purpose

This PRD defines the requirements for **Lumora Probe Lite** — a minimal, no-frill DICOM
receiver for CLI use. It stores received DICOM instances to disk and logs all activity to
stdout. Nothing more.

This is a debugging tool, not a platform. It answers one question: *"Is my DICOM sender
actually delivering instances, and what exactly is it sending?"*

## 1.2 Relationship to Lumora Probe

Lumora Probe Lite lives in the same repository as Lumora Probe but is an **independent
codebase**. It shares no source code with the parent project. It does not use the parent's
event bus, capture format, plugin system, web UI, or database layer.

It may informally validate assumptions that later feed into the full Lumora Probe, but it
has no dependency on the parent's architecture and the parent has no dependency on it.

## 1.3 Scope

Lumora Probe Lite is:

- A DICOM C-STORE SCP (receiver)
- A DICOM C-ECHO SCP (verification)
- A file writer that saves received instances in a Study/Series/Instance directory hierarchy
- A stdout logger for all association and transfer activity

Lumora Probe Lite is **not**:

- A PACS or archive
- A DICOM viewer
- A capture/replay tool
- A query server (no C-FIND, C-MOVE, C-GET)
- A web application
- A plugin host
- A multi-node or distributed system

---

# 2. Target Users

- PACS administrators verifying sender connectivity
- Integration engineers debugging C-STORE failures
- Vendor support engineers confirming what a modality actually sends
- Developers testing DICOM client implementations
- QA engineers validating transfer syntax negotiation

All users are technical. No clinical users.

---

# 3. Product Principles

1. **Zero config to start.** `probe-lite` with no arguments listens and receives.
2. **Stdout is the UI.** No log files, no database, no web dashboard.
3. **Fail loudly.** Errors go to stdout with cause and context. Never swallow.
4. **No magic.** What arrives on the wire is what lands on disk. No transformation, no
   de-identification, no normalization.
5. **Small dependency surface.** pynetdicom + pydicom + standard library. Nothing else
   without justification.

---

# 4. Functional Requirements

## 4.1 DICOM Networking

### FR-01: C-STORE SCP

The tool shall accept DICOM C-STORE requests and store received datasets to disk.

- Accept all SOP Classes proposed by the requestor (no hardcoded whitelist in v1).
- Accept all Transfer Syntaxes proposed by the requestor.
- Return appropriate DICOM status codes:
  - `0x0000` (Success) when the instance is written to disk.
  - `0xA700` (Refused: Out of Resources) when disk write fails.
  - `0xA900` (Error: Data Set does not match SOP Class) when the dataset is invalid.
  - `0xC000–0xCFFF` (Error: Cannot understand) for malformed requests.

### FR-02: C-ECHO SCP

The tool shall respond to C-ECHO (Verification) requests with `0x0000` (Success).

This allows senders to confirm connectivity and AE title negotiation before sending data.

### FR-03: Association Negotiation

- Accept associations from **any** Calling AE Title by default.
- Support optional `--accept-ae` flag to restrict accepted Calling AE Titles (comma-separated
  list). Associations from unlisted AEs are rejected with an appropriate DICOM reject result.
- Maximum PDU length: configurable via `--max-pdu` (default: 16382, pynetdicom default).
- Support multiple simultaneous associations (pynetdicom thread-per-association model).

### FR-04: Transfer Syntax Handling

- Accept all standard Transfer Syntaxes (Implicit VR LE, Explicit VR LE, Explicit VR BE,
  all JPEG variants, JPEG 2000, JPEG-LS, RLE, etc.).
- Store the dataset exactly as received — no transcoding.
- Log the negotiated Transfer Syntax UID for each instance.

## 4.2 Storage

### FR-05: Directory Hierarchy

Received instances shall be stored in a three-level hierarchy:

```
<output-dir>/
  <StudyInstanceUID>/
    <SeriesInstanceUID>/
      <SOPInstanceUID>.dcm
```

- Default output directory: `./received` (current working directory).
- Configurable via `--output` / `-o` flag or `PROBE_LITE_OUTPUT` env var.
- Directories are created on demand.
- The `.dcm` extension is always appended.
- If a file already exists at the target path, it is **overwritten** silently (idempotent
  receive). No duplicate detection in v1.

### FR-06: File Integrity

- Write the received dataset byte-faithfully using pydicom's `dcmwrite`.
- Preserve the original Transfer Syntax (no implicit conversion).
- If the dataset cannot be parsed by pydicom, write the raw bytes to
  `<SOPInstanceUID>.dcm.raw` and log a warning. Never drop data silently.

## 4.3 Logging

### FR-07: Stdout Logging

All activity is logged to **stdout**. No log files are created.

Events logged:

| Event | Fields |
|-------|--------|
| Startup | Port, AE Title, output directory, accepted AEs (if restricted) |
| Association requested | Calling AE, Called AE, peer address:port |
| Association accepted | Calling AE, negotiated presentation contexts count |
| Association rejected | Calling AE, peer address, reject reason |
| Association released | Calling AE, peer address, duration, instances received |
| Association aborted | Calling AE, peer address, abort source |
| Instance received | SOP Instance UID, SOP Class UID, Transfer Syntax, Study UID, Series UID, file path, size in bytes |
| Instance store failed | SOP Instance UID, error cause |
| C-ECHO received | Calling AE, peer address |
| Shutdown | Total instances received, total associations, uptime |

### FR-08: Log Format

Two formats, selected via `--format`:

- `text` (default): Human-readable, one line per event. Timestamps in local time with
  millisecond precision. Example:

  ```
  14:32:01.123 [INFO] Association accepted: CALLING_AE=CT_SCANNER peer=192.168.1.50:54321 contexts=12
  14:32:01.456 [INFO] Instance received: 1.2.840.113619.2.55.3.123 CT 1.2.840.10008.1.2.1 Study/1.2.3/4.5.6/7.8.9.dcm 524288 bytes
  ```

- `json`: Structured JSON Lines (one JSON object per line). Each object includes at minimum:
  `timestamp` (ISO 8601 UTC), `level`, `event`, and event-specific fields.

### FR-09: Verbosity

- `--verbose` / `-v`: Include additional DICOM negotiation detail (full presentation context
  list, extended negotiation items).
- Without `--verbose`: Log the events in FR-07 only.
- Errors and warnings are always logged regardless of verbosity.

## 4.4 CLI Interface

### FR-10: Command and Arguments

Invocation: `probe-lite`

| Argument | Short | Env Var | Default | Description |
|----------|-------|---------|---------|-------------|
| `--port` | `-p` | `PROBE_LITE_PORT` | `11112` | TCP listen port |
| `--ae` | `-a` | `PROBE_LITE_AE` | `PROBE_LITE` | Called AE Title |
| `--output` | `-o` | `PROBE_LITE_OUTPUT` | `./received` | Instance storage directory |
| `--accept-ae` | | `PROBE_LITE_ACCEPT_AE` | *(any)* | Comma-separated Calling AE whitelist |
| `--format` | `-f` | `PROBE_LITE_FORMAT` | `text` | Log format: `text` or `json` |
| `--max-pdu` | | `PROBE_LITE_MAX_PDU` | `16382` | Maximum PDU length in bytes |
| `--verbose` | `-v` | `PROBE_LITE_VERBOSE` | `false` | Verbose negotiation logging |
| `--version` | | | | Print version and exit |
| `--help` | `-h` | | | Print usage and exit |

Precedence: CLI argument > environment variable > default.

### FR-11: Lifecycle

- Start: Bind port, log startup line, begin accepting associations.
- Run: Accept and serve associations until interrupted.
- Stop: `SIGINT` (Ctrl+C) or `SIGTERM`. Stop accepting new associations, wait for active
  associations to complete (grace period: 5 seconds), log shutdown summary, exit 0.
- If the port is already in use, log the error and exit 1 immediately.

---

# 5. Non-Functional Requirements

## NFR-01: Startup Time

Cold start to listening in under 1 second on commodity hardware.

## NFR-02: Memory

No unbounded growth. Memory usage should remain proportional to the number of active
associations, not the number of instances received. Datasets are written to disk and
released, not accumulated in memory.

## NFR-03: Disk

No artificial limit on stored data. The tool writes until disk is full, then reports
errors per FR-01 (`0xA700`). No cleanup, no retention policy, no rotation.

## NFR-04: Platforms

Python 3.13+. macOS, Linux, Windows. No platform-specific code paths.

## NFR-05: Dependencies

Runtime dependencies:

- `pynetdicom` — DICOM networking
- `pydicom` — DICOM dataset parsing and serialization

No other runtime dependencies without an ADR-equivalent justification recorded in this PRD.

## NFR-06: Concurrency

Multiple simultaneous associations handled via pynetdicom's native threading model.
No custom concurrency code in v1. Thread safety is delegated to pynetdicom and the
filesystem.

## NFR-07: Security

None. No authentication, no TLS, no AE-based access control beyond the optional
`--accept-ae` whitelist. This is a debugging tool for trusted networks. Document this
explicitly in `--help` output: *"No security. Use on trusted networks only."*

---

# 6. Technical Constraints

## TC-01: Repository Layout

Lumora Probe Lite is an independent package within the `lumora-probe` repository. It does
not import from or share code with the parent `lumora/` package.

Proposed layout:

```
src/probe_lite/
  __init__.py
  __main__.py       # entry point: python -m probe_lite
  cli.py            # argument parsing
  receiver.py       # pynetdicom SCP setup, handlers
  storage.py        # disk write logic
  logging.py        # stdout formatting (text + json)
pyproject.toml      # [project.scripts] probe-lite = "probe_lite.cli:main"
```

This layout is a recommendation, not a binding constraint. The implementer may adjust
internal structure as long as the package remains independent from `lumora/`.

## TC-02: Toolchain

Consistent with the parent project where practical:

- `uv` for dependency management
- `ruff` for formatting and linting
- `pytest` for tests
- Python 3.13+

## TC-03: No Web, No Database, No Config Files

The tool has no HTTP server, no REST API, no WebSocket, no SQLite, no TOML/YAML config
file. All configuration is via CLI arguments and environment variables (FR-10).

---

# 7. Testing Requirements

## TR-01: Synthetic Data Only

All test DICOM data is generated programmatically with pydicom. No real patient data,
not even de-identified.

## TR-02: Required Test Scenarios

| Scenario | Type |
|----------|------|
| C-ECHO round-trip (loopback) | Integration |
| C-STORE single instance, verify file on disk | Integration |
| C-STORE multiple instances across Study/Series | Integration |
| Multiple simultaneous associations | Integration |
| Association from rejected AE (with `--accept-ae`) | Integration |
| Unparseable dataset → `.raw` fallback | Unit |
| Disk full / write failure → `0xA700` status | Unit (mocked) |
| CLI argument parsing and env var precedence | Unit |
| JSON log format validity (parseable JSONL) | Unit |
| Graceful shutdown on SIGINT | Integration |

## TR-03: Interop (Optional)

Interop testing against DCMTK (`storescu`, `echoscu`) is desirable but not a gate.
Document as a manual verification step.

---

# 8. Definition of Done

Lumora Probe Lite v1 is complete when:

1. `probe-lite` with no arguments starts a C-STORE + C-ECHO SCP on port 11112.
2. Instances sent by `storescu` (or equivalent) land in `./received/<Study>/<Series>/<Instance>.dcm`.
3. All events from FR-07 appear on stdout in the selected format.
4. `--format json` produces valid JSON Lines parseable by `jq`.
5. Multiple simultaneous associations are handled without error.
6. `--accept-ae` rejects unlisted Calling AEs.
7. Ctrl+C produces a clean shutdown with summary line.
8. All tests in TR-02 pass.
9. `ruff check` and `ruff format --check` pass.
10. `--help` output is complete and accurate.

---

# 9. Explicit Non-Goals (v1)

The following are **out of scope** and must not be implemented:

- C-FIND, C-MOVE, C-GET, C-WORKLIST
- DICOMweb / STOW-RS
- TLS / DICOM Secure Negotiation
- De-identification or anonymization
- Duplicate instance detection
- Storage commitment
- SOP Class filtering / whitelist
- Transfer syntax transcoding
- Log file output
- Configuration files (TOML, YAML, INI)
- Web UI or REST API
- Database or index
- Capture/replay
- Plugin system
- Metrics / Prometheus
- Docker packaging
- Auto-restart / service management

Any of these may be considered for a future version with a PRD amendment.

---

# 10. Success Criteria

A user can:

1. Run `probe-lite` on a laptop.
2. Point a modality or `storescu` at it.
3. See every association and instance logged in real time on stdout.
4. Find the received files in a predictable directory structure.
5. Pipe `--format json` output into `jq` for scripted analysis.
6. Confirm C-ECHO connectivity before sending data.

If all six work, the tool has succeeded.
