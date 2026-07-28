# Lumora Sender Lite — Detailed Implementation Plan

- **Status:** Approved for implementation
- **Plan date:** 2026-07-28
- **Target repository:** `lumora-probe`
- **Implementation target:** a less-capable coding model
- **Instruction:** implement only this plan; do not broaden scope

## 1. Objective

Add a one-shot DICOM C-STORE sender as Probe Lite's test counterpart.

A normal Sender Run must:

1. Resolve configuration from TOML, CLI overrides, and defaults.
2. Recursively scan one input directory.
3. Build an in-memory Catalog grouped by Study, Series, and Instance.
4. Reject malformed, inconsistent, duplicate, or otherwise unsendable files without stopping the scan.
5. Send each Study Batch over exactly one DICOM association.
6. Release that association after the Study's Instances have outcomes.
7. Wait the configured delay before starting the next Study.
8. Continue after non-cancellation failures.
9. Emit deterministic text or JSONL diagnostics and a final summary.
10. Exit with an automation-safe status code.

An optional Echo Run must test DICOM Verification connectivity and exit without scanning.

## 2. Scope boundary

### In scope

- CPython 3.13+.
- Windows, macOS, Linux.
- `pydicom>=3,<4` and `pynetdicom>=3,<4`, already installed.
- Plain DICOM TCP associations on trusted engineering networks.
- C-ECHO SCU in explicit diagnostic mode.
- C-STORE SCU in normal mode.
- TOML configuration via stdlib `tomllib`.
- CLI > TOML > defaults precedence.
- Sequential Study Batches and sequential Instance sends.
- Exact original transfer-syntax negotiation; no transcoding.
- Existing Probe Lite as the primary integration-test SCP.

### Explicit non-goals

- GUI or interactive selection.
- Directory watching, daemon mode, or persistent workers.
- Parallel associations or concurrent DIMSE requests.
- Retry, resume, checkpoint, or persistent queue.
- Persistent Catalog or manifest export.
- Study filtering or selection.
- Dataset modification, anonymization, UID generation, transcoding, decompression, recompression, or normalization.
- C-FIND, C-MOVE, C-GET, Storage Commitment, or DICOMweb.
- TLS, authentication, certificate handling, or production security claims.
- Environment-variable configuration.
- Config includes, profiles, or parent/home-directory search.

## 3. Current repository baseline

Preserve these established patterns:

- `probe_lite/config.py`: frozen slotted configuration dataclass, explicit validation, argparse entry point.
- `probe_lite/log.py`: dependency-free stdout-only text/JSONL event logging.
- `probe_lite/receiver.py`: direct `pynetdicom.AE` lifecycle, explicit association events, no global logging configuration.
- `probe_lite/cli.py`: integer exit codes and portable signal handling.
- `tests/test_receiver.py`: in-process ProbeReceiver, generated DICOM fixtures, transfer-syntax round trips.
- Root `pyproject.toml`: Hatchling, Ruff, Pytest, CPython 3.13, cross-platform package.

Do not overwrite existing uncommitted changes in:

- `probe_lite/__main__.py`
- `pyproject.toml`
- `uv.lock`

Merge Sender Lite packaging edits into the current `pyproject.toml` state.

## 4. Settled domain language

Canonical definitions live in `/CONTEXT.md`.

- **Catalog:** in-memory inventory of sendable files grouped by Study and Series.
- **Sendable Instance:** one DICOM file with identifiers and transfer metadata required for C-STORE.
- **Catalog Conflict:** multiple discovered files claiming one SOP Instance UID; all copies are excluded.
- **Study Batch:** all Series and Instances sharing one Study Instance UID.
- **Study Association:** the one association used for one Study Batch.
- **Sender Run:** catalog, send all Study Batches, exit.
- **Echo Run:** one explicit C-ECHO operation, no cataloging, exit.

Use these names in modules, logs, tests, and documentation. Avoid overloaded terms such as “job,” “package,” or “single transfer.”

## 5. Architectural decision

`docs/adr/ADR-0027-sender-study-association-boundary.md` is binding:

- one Study Batch = one Study Association;
- one context per unique `(SOPClassUID, TransferSyntaxUID)` pair;
- sequential C-STORE requests;
- no transcoding;
- no Study splitting;
- more than 128 required contexts = Study preflight failure;
- association release, then inter-study delay.

## 6. Package and file layout

Add this minimal package:

```text
sender_lite/
├── __init__.py      # package description and version import/constant
├── __main__.py      # python -m sender_lite
├── cli.py           # orchestration, cancellation, exit-code mapping
├── config.py        # argparse, TOML loading, merge, path resolution, validation
├── catalog.py       # scan, validate, deduplicate, group, deterministic ordering
├── log.py           # SenderLogger text/JSONL events
└── sender.py        # C-ECHO and Study Association/C-STORE behavior
```

Add tests:

```text
tests/
├── test_sender_config.py
├── test_sender_catalog.py
├── test_sender_logging.py
├── test_sender_transport.py
└── test_sender_cli.py
```

Do not add `models.py`, service containers, repositories, protocols, or plugin abstractions. Keep small dataclasses next to the code that owns them.

## 7. Configuration contract

### 7.1 Commands

Primary forms:

```console
sender-lite
python -m sender_lite
sender-lite --config ./sender-lite.toml
sender-lite --input ./dicom --host 127.0.0.1 --port 11112
sender-lite --echo
sender-lite --echo --config ./sender-lite.toml
```

`--help` and `--version` bypass config discovery and validation.

### 7.2 Sources and precedence

Resolution order:

1. Parse enough CLI state to identify `--help`, `--version`, and `--config`.
2. If `--config PATH` exists, load that file.
3. Otherwise, if `./sender-lite.toml` exists, load it automatically.
4. If invocation has zero arguments and no default config exists, raise a configuration error.
5. Merge explicit CLI values over TOML values.
6. Fill omitted optional values from defaults.
7. Resolve paths according to their source.
8. Validate the fully resolved configuration.

Path rules:

- TOML-relative `input`: relative to the TOML file's parent directory.
- CLI-relative `--input`: relative to current working directory.
- Explicit `--config`: resolve from current working directory before loading.
- Automatically discovered config: exactly `./sender-lite.toml`; do not search parents, home, or OS config directories.

Unknown TOML keys are errors. Wrong TOML value types are errors. Do not silently coerce arbitrary strings into numbers or booleans.

### 7.3 Config fields

| Field | CLI | TOML | Default | Validation |
|---|---|---|---|---|
| config path | `--config PATH` | n/a | auto-discover `./sender-lite.toml` | regular readable file |
| input | `--input`, `-i` | `input` | required in Sender Run | existing readable directory; not symlink |
| host | `--host` | `host` | `127.0.0.1` | non-empty string |
| port | `--port`, `-p` | `port` | `11112` | integer `1..65535` |
| calling AE | `--calling-ae` | `calling_ae` | `SENDER_LITE` | 1–16 ASCII chars |
| called AE | `--called-ae` | `called_ae` | `PROBE_LITE` | 1–16 ASCII chars |
| study delay | `--study-delay` | `study_delay` | `1.0` | finite number `>=0` |
| connect timeout | `--connect-timeout` | `connect_timeout` | `10.0` | finite number `>0` |
| DIMSE timeout | `--dimse-timeout` | `dimse_timeout` | `30.0` | finite number `>0` |
| max PDU | `--max-pdu` | `max_pdu` | `16382` | integer `1..16777215` |
| log format | `--format`, `-f` | `log_format` | `text` | `text` or `json` |
| verbose | `--verbose`, `-v`; `--no-verbose` | `verbose` | `false` | boolean |
| mode | `--echo` | n/a | Sender Run | CLI flag only |

Use a frozen slotted `Config` dataclass. Suggested fields:

```text
input: Path | None
host: str
port: int
calling_ae: str
called_ae: str
study_delay: float
connect_timeout: float
dimse_timeout: float
max_pdu: int
log_format: str
verbose: bool
echo: bool
config_path: Path | None
```

`input=None` is valid only when `echo=True`.

### 7.4 TOML example

```toml
input = "./dicom"
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

Keep the file flat. Do not introduce a `[sender]` table.

### 7.5 Configuration errors

All configuration failures:

- print one concise `sender-lite: configuration error: ...` line to stdout;
- include help guidance, not a Python traceback;
- return exit code `2`;
- occur before Catalog scanning or networking.

## 8. Catalog model

### 8.1 Records

Define immutable records in `sender_lite/catalog.py`.

`CatalogInstance` fields:

- `path: Path`
- `size_bytes: int`
- `study_uid: str`
- `series_uid: str`
- `sop_instance_uid: str`
- `sop_class_uid: str`
- `transfer_syntax_uid: str`
- `instance_number: int | None`

`SeriesCatalog` fields:

- `series_uid: str`
- `instances: tuple[CatalogInstance, ...]`

`StudyBatch` fields:

- `study_uid: str`
- `series: tuple[SeriesCatalog, ...]`
- derived/explicit flattened ordered Instances
- derived/explicit unique presentation requirements
- aggregate bytes and Instance counts

`CatalogIssue` fields:

- `path: Path`
- stable reason code
- human-readable error
- optional SOP Instance UID for duplicate conflicts

`Catalog` fields:

- `studies: tuple[StudyBatch, ...]`
- `issues: tuple[CatalogIssue, ...]`
- scanned file count
- rejected file count
- sendable Instance count
- Series count
- Study count
- total sendable bytes

Prefer derived properties when trivial; store aggregates only when this avoids repeated tree walks in reporting.

### 8.2 Traversal

Algorithm:

1. Validate the input root before scanning.
2. Recursively enumerate entries without following symlinked directories.
3. Skip every symlink, including symlinked files.
4. Consider every regular file regardless of extension.
5. Sort candidate paths lexically before reading so diagnostics are reproducible.
6. Handle per-entry permission/stat/read errors as Catalog issues and continue.
7. A root-level traversal failure that prevents meaningful scanning is a runtime failure.

Do not use filename extensions to identify DICOM.

### 8.3 Metadata read

For each candidate:

- call `pydicom.dcmread(path, stop_before_pixels=True, force=False)`;
- do not load Pixel Data during cataloging;
- do not use forced parsing;
- do not mutate the dataset;
- capture file size from the filesystem;
- convert required values to canonical strings only after validating presence and multiplicity.

A DICOMDIR or other DICOM object lacking required Study/Series/Instance identity is rejected normally.

### 8.4 Admission validation

Require:

- `StudyInstanceUID`;
- `SeriesInstanceUID`;
- `SOPInstanceUID`;
- `SOPClassUID`;
- file-meta `MediaStorageSOPInstanceUID`;
- file-meta `MediaStorageSOPClassUID`;
- file-meta `TransferSyntaxUID`.

For each UID:

- construct/use `pydicom.uid.UID`;
- require `is_valid`;
- require length `<=64`;
- reject empty or multi-valued identifiers.

Consistency requirements:

- dataset SOP Class UID equals file-meta Media Storage SOP Class UID;
- dataset SOP Instance UID equals file-meta Media Storage SOP Instance UID;
- transfer syntax UID is valid and `is_transfer_syntax`;
- private Study/Series/SOP Class/SOP Instance UIDs remain allowed when syntactically valid;
- optional clinical/descriptive attributes are irrelevant.

`InstanceNumber` handling:

- accept a single integer or integer-like decimal string;
- reject no file solely because Instance Number is absent or invalid;
- store invalid/missing Instance Number as `None` and optionally log only in verbose mode.

### 8.5 Duplicate SOP Instance UID handling

Use a two-stage accumulation process:

1. Parse all individually admissible candidates.
2. Group them by SOP Instance UID.
3. A group of size one remains sendable.
4. A group of size greater than one becomes a Catalog Conflict.
5. Exclude every file in that conflict group.
6. Emit one issue per conflicting path with the same reason code.

Do not compare file hashes and do not select a winner.

### 8.6 Grouping and deterministic ordering

After duplicate removal:

- merge files with the same Study Instance UID into one Study Batch regardless of source folder;
- group each Study by Series Instance UID;
- Study order: ascending Study Instance UID;
- Series order: ascending Series Instance UID;
- Instance order within a Series:
  1. Instances with a usable Instance Number;
  2. ascending numeric Instance Number;
  3. ascending SOP Instance UID as tie-breaker;
  4. unnumbered Instances after numbered Instances;
  5. ascending SOP Instance UID among unnumbered Instances.

### 8.7 Empty Catalog

Complete the scan and emit the Catalog summary. If zero Sendable Instances remain:

- do not open a network connection;
- emit `run_failed` with reason `empty_catalog`;
- exit `1`.

## 9. Presentation-context planning

For each Study Batch:

1. Build the unique set of exact `(SOP Class UID, Transfer Syntax UID)` pairs.
2. Sort pairs by SOP Class UID, then transfer syntax UID.
3. Build one requested presentation context per pair.
4. Do not combine several transfer syntaxes into one context: the acceptor selects one syntax per accepted context, and mixed-encoding Instances need exact accepted matches.
5. If pair count exceeds 128, fail the Study preflight.
6. Do not open an association for that Study.
7. Mark all its Instances failed with reason `presentation_context_limit`.
8. Continue to the inter-study delay and next Study unless cancelled.

Do not fall back to “all storage contexts”; request only what the Study requires.

## 10. Sender transport

### 10.1 Sender object

Implement `Sender` in `sender_lite/sender.py` with explicit operations:

- `echo() -> EchoResult`
- `send_study(study: StudyBatch, cancel_event: threading.Event) -> StudyResult`

The constructor receives resolved `Config` and `SenderLogger`. Avoid hidden global state.

Use small immutable result records for Echo, Instance, Study, and Run summaries. Outcomes must be inspectable by tests without parsing logs.

### 10.2 AE configuration

Build a fresh `pynetdicom.AE` for each Echo Run or Study Batch.

Set:

- local AE title from `calling_ae`;
- `connection_timeout = connect_timeout`;
- `acse_timeout = connect_timeout`;
- `dimse_timeout = dimse_timeout`;
- `network_timeout = dimse_timeout`;
- association `max_pdu = config.max_pdu`;
- peer address from `host`, `port`;
- Called AE title from `called_ae`.

Fresh AE-per-Study prevents presentation contexts leaking between Studies and keeps the one-Study boundary visible.

### 10.3 Study Association lifecycle

For a preflight-valid Study:

1. Emit `study_started`.
2. Build the exact requested contexts.
3. Request the association.
4. If not established, classify rejection/abort/timeout where possible.
5. Mark every Instance failed when association establishment fails.
6. If established, capture accepted and rejected contexts.
7. Match accepted contexts by exact SOP Class UID and transfer syntax UID.
8. Instances lacking an exact accepted context are failed without calling C-STORE.
9. Iterate accepted Instances in Catalog order.
10. Before each send, check cancellation.
11. Re-read and revalidate the full dataset.
12. Send one C-STORE and wait synchronously for its response.
13. Record success, warning, or failure.
14. Continue after a DICOM failure response while the association remains established.
15. If association is lost/aborted or response is absent, fail the current Instance and every unsent Instance.
16. Release a healthy association after all possible sends.
17. Abort an unusable or cancelled active association.
18. Emit `study_completed` with aggregates and duration.

Do not create a replacement association for the same Study.

### 10.4 Full-file revalidation

Immediately before C-STORE:

- verify path still exists and is a regular non-symlink file;
- full-read with `pydicom.dcmread(path, force=False)`;
- re-run required UID and file-meta consistency checks;
- require Study UID, Series UID, SOP Instance UID, SOP Class UID, and transfer syntax to equal Catalog values;
- file size may change only if the DICOM transmission metadata remains identical; report the actual send-time size;
- any read or identity change is an Instance failure;
- do not hash or stage files.

### 10.5 Message IDs

Use monotonically increasing C-STORE Message IDs within one Study Association. Start at `1`; wrap after `65535` if ever required. Never issue concurrent requests, so reuse after wrap is safe only after the previous response completed.

### 10.6 C-STORE status classification

Read `status.Status` defensively.

- `0x0000`: success.
- `0xB000..0xBFFF`: warning.
- any other numeric status: failure.
- missing Status, empty response, timeout, exception, abort, or connection loss: failure.

Warnings:

- emit warning-level output;
- count separately;
- do not stop the Study;
- do not alone make the final process exit nonzero.

### 10.7 Failure continuation

- Per-Instance DICOM failure: continue if association remains usable.
- Exact context rejected: fail affected Instances; continue accepted ones.
- Association establishment failure: fail all Study Instances.
- Mid-Study association loss: fail current and unsent Instances.
- File revalidation failure: fail that Instance; continue.
- No automatic retry anywhere.

## 11. Inter-study delay

After every Study Batch except the final one:

1. Emit `study_delay_started` with delay seconds and next Study UID.
2. Wait `study_delay` seconds.
3. Use cancellation-aware waiting, such as `cancel_event.wait(timeout)`, not unconditional `time.sleep`.
4. Continue immediately when delay is `0`.
5. Apply delay after successful and failed Studies, including preflight failures.
6. Do not delay after the final Study.
7. Cancellation ends the wait immediately.

## 12. Echo Run

Echo mode is CLI-only via `--echo`; it is not a TOML key.

Flow:

1. Resolve config normally, but do not require `input`.
2. Do not scan.
3. Build a fresh AE with the configured Calling AE and timeouts.
4. Request only the Verification SOP Class using pynetdicom's default Verification transfer syntaxes.
5. Associate with configured host, port, Called AE, and max PDU.
6. If established, send one C-ECHO.
7. Release a healthy association.
8. Report response status and duration.
9. Exit `0` only for `0x0000`; otherwise exit `1`.

Do not perform automatic C-ECHO before normal C-STORE sends.

## 13. Cancellation and signals

Reuse Probe Lite's portable signal approach, adapted for incomplete outbound work.

- Main thread installs handlers for available `SIGINT`, `SIGTERM`, and `SIGBREAK`.
- First signal sets one cancellation Event and logs `cancellation_requested`.
- Never start another C-STORE or Study after cancellation.
- Abort an active association when an operation is pending; release if no operation is pending and release is still safe.
- Mark remaining Instances `cancelled`, not `failed`.
- Interrupt inter-study delay immediately.
- Emit partial Study and Run summaries.
- Return `130` for cancellation.
- A second interrupt may raise/terminate immediately.
- Restore previous signal handlers in `finally`.

Tests must not depend on POSIX-only signals.

## 14. Logging contract

### 14.1 Logger shape

Implement `SenderLogger` using ProbeLogger's behavior, not Python global logging:

- stdout only;
- UTC timestamp in JSONL;
- local timestamp in text;
- one event per line;
- flush every event;
- `info`, `warning`, `error` helpers;
- `json.dumps(..., default=str)` for paths and UIDs;
- no PHI fields.

Do not refactor ProbeLogger into shared infrastructure in this phase.

### 14.2 Required events

| Event | Level | Required fields |
|---|---|---|
| `configuration_resolved` | INFO | mode, config path, input if applicable, host, port, Calling AE, Called AE, delay, timeouts, max PDU, format, verbose |
| `scan_started` | INFO | input |
| `file_skipped` | WARNING | path, reason code, error |
| `catalog_conflict` | ERROR | path, SOP Instance UID, conflicting count |
| `scan_completed` | INFO | files scanned, rejected, Studies, Series, Instances, bytes, duration |
| `study_started` | INFO | Study UID, Series, Instances, bytes, context count, ordinal/total |
| `association_accepted` | INFO | Study UID, peer, accepted/rejected context counts |
| `association_rejected` | ERROR | Study UID, peer, reason if available |
| `association_aborted` | ERROR | Study UID, peer, phase |
| `presentation_context_rejected` | ERROR | Study UID, SOP Class UID, transfer syntax UID, affected Instance count |
| `instance_sent` | INFO | Study/Series/SOP UIDs, SOP Class UID, transfer syntax, path, bytes, status, duration |
| `instance_warning` | WARNING | same correlation fields plus status |
| `instance_failed` | ERROR | same available correlation fields, reason, status if present |
| `study_completed` | INFO/ERROR | attempted, succeeded, warned, failed, cancelled, duration |
| `study_delay_started` | INFO | seconds, next Study UID |
| `echo_completed` | INFO/ERROR | peer, status, duration |
| `cancellation_requested` | WARNING | signal |
| `run_completed` | INFO/ERROR | all aggregate counts, duration, exit code |
| `run_failed` | ERROR | reason, error, exit code |

Verbose mode adds requested/accepted presentation-context detail and association negotiation identifiers. It must not enable pynetdicom's global debug logger.

### 14.3 PHI rule

Never log:

- Patient Name;
- Patient ID;
- accession number;
- dates of birth;
- Study/Series descriptions;
- free-text dataset values;
- full dataset dumps.

UIDs and source paths are allowed for engineering correlation. Document that source paths may themselves contain sensitive text.

## 15. Exit codes

| Code | Meaning |
|---|---|
| `0` | all attempted Instances succeeded or warned; or Echo succeeded |
| `1` | any Instance/Study failed, empty Catalog, Echo failure, or unexpected runtime/I/O/network error |
| `2` | invalid CLI/TOML configuration or usage |
| `130` | interrupted/cancelled before completion |

A warning-only run exits `0`. A partially successful run containing one failure exits `1`.

## 16. CLI orchestration

`sender_lite.cli.main(argv=None) -> int` sequence:

```text
parse/resolve config
if config error: print concise error; return 2
create logger
log resolved config
install cancellation handlers
if echo:
    run echo
    map result to 0/1
else:
    build Catalog
    if empty: return 1
    for Study in deterministic order:
        if cancelled: stop
        send Study
        aggregate result
        if another Study remains: cancellation-aware delay
    return 130 if cancelled else 1 if any failure else 0
always restore handlers
always emit final summary after logger exists
```

Avoid catching `BaseException`. Catch expected configuration, filesystem, pydicom, pynetdicom, timeout, and runtime exceptions at the narrowest layer. Convert unexpected top-level exceptions to `run_failed`/exit `1` without exposing a traceback during normal CLI operation. Tests may exercise the underlying exception directly at lower layers.

## 17. Packaging changes

Modify root `pyproject.toml` carefully:

- retain existing project name and version unless release policy later requires a bump;
- update description/readme language to cover receiver and sender tools;
- retain current dependencies and constraints;
- add script `sender-lite = "sender_lite.cli:main"`;
- retain `probe-lite` and `probe_lite` scripts;
- change Hatch wheel package list from only `probe_lite` to both `probe_lite` and `sender_lite`;
- do not create a nested project or second lockfile.

Update root `README.md` with:

- receiver and sender distinction;
- Sender Lite install/run/config examples;
- default `sender-lite.toml` discovery;
- Echo Run example;
- Study Batch behavior;
- trusted-network warning;
- exit codes;
- test commands.

Add `docs/sender_lite/README.md` only if a shorter operator guide is useful after implementation. Do not duplicate this plan verbatim.

## 18. Detailed implementation sequence

### Phase 1 — Package skeleton and config

Files:

- `sender_lite/__init__.py`
- `sender_lite/__main__.py`
- `sender_lite/config.py`
- `tests/test_sender_config.py`

Tasks:

1. Add package metadata and module entry point matching the existing cross-platform pattern.
2. Define defaults and frozen slotted Config.
3. Build argparse with explicit `None` defaults so CLI provenance is detectable.
4. Implement early help/version behavior.
5. Implement explicit and automatic TOML discovery.
6. Validate flat TOML keys and native types.
7. Merge CLI > TOML > defaults.
8. Resolve source-relative paths correctly.
9. Validate mode-specific required fields.
10. Cover every precedence and failure branch before networking work.

Gate:

- every config test passes;
- zero args + no config returns `2`;
- zero args + default config resolves;
- `--echo` + default config does not require input;
- CLI false can override TOML `verbose=true` via `--no-verbose`.

### Phase 2 — Catalog

Files:

- `sender_lite/catalog.py`
- `tests/test_sender_catalog.py`

Tasks:

1. Add immutable Catalog records.
2. Implement non-symlink recursive traversal.
3. Add metadata-only parse.
4. Add strict identifier/file-meta checks.
5. Add Instance Number normalization.
6. Add duplicate conflict elimination.
7. Add grouping and deterministic ordering.
8. Add aggregate counts and issue reporting.
9. Add empty-Catalog behavior at orchestration boundary.

Gate:

- arbitrary extensions work;
- non-DICOM and malformed files are skipped;
- symlinks are skipped;
- missing/mismatched metadata is rejected;
- all copies of duplicate SOP Instance UIDs are excluded;
- Study/Series/Instance ordering exactly matches section 8.6.

### Phase 3 — Logger and result records

Files:

- `sender_lite/log.py`
- result records in owner modules
- `tests/test_sender_logging.py`

Tasks:

1. Mirror ProbeLogger's text/JSONL contract.
2. Add required event labels.
3. Ensure one-line output and stable field names.
4. Verify JSON types/serialization.
5. Add a PHI-field regression assertion for representative events.

Gate:

- JSON output parses one object per line;
- text output remains one line per event;
- no event includes clinical metadata fields.

### Phase 4 — Echo and Study transport

Files:

- `sender_lite/sender.py`
- `tests/test_sender_transport.py`

Tasks:

1. Build AE factory/configuration privately inside Sender.
2. Implement Echo Run.
3. Implement exact presentation requirements.
4. Enforce 128-context Study cap.
5. Implement association outcome classification.
6. Map accepted contexts exactly.
7. Add full-file revalidation.
8. Implement sequential C-STORE with message IDs.
9. Classify success/warning/failure statuses.
10. Handle context rejection, association loss, abort, and timeout.
11. Release or abort deterministically.
12. Return structured Study results.

Gate:

- no network call for over-limit Study;
- no C-STORE for rejected context;
- no second association for a failed Study;
- mixed accepted/rejected Instances produce partial Study result;
- warning does not become failure;
- exact transfer syntax is preserved.

### Phase 5 — CLI lifecycle and delay

Files:

- `sender_lite/cli.py`
- `tests/test_sender_cli.py`

Tasks:

1. Connect config, logger, Catalog, and Sender.
2. Add portable first-signal cancellation.
3. Add second-interrupt immediate behavior.
4. Add cancellation-aware inter-study delay.
5. Aggregate Study results.
6. Map exact exit codes.
7. Guarantee final summary and handler restoration.

Gate:

- one Study causes one association and no delay;
- multiple Studies cause one association each and `N-1` waits;
- failure still proceeds after delay;
- cancellation stops new sends and returns `130`;
- partial failure returns `1`.

### Phase 6 — Packaging, integration, documentation

Files:

- `pyproject.toml`
- `README.md`
- integration portions of sender tests

Tasks:

1. Add Sender package to Hatch target.
2. Add `sender-lite` script.
3. Update repository description/docs without breaking Probe Lite commands.
4. Run Sender against in-process ProbeReceiver.
5. Verify receiver storage hierarchy and transfer syntax.
6. Run full test/lint/format suite.
7. Verify wheel contains both packages and all three commands.

Gate:

- installed `probe-lite`, `probe_lite`, `sender-lite`, and both module invocations work;
- receiver tests remain green;
- Sender integration tests pass on Windows, macOS, Linux CI.

## 19. Test matrix

### 19.1 Configuration

Test:

- complete defaults in CLI-driven Sender Run except required input;
- automatic `sender-lite.toml` discovery;
- zero args/no config error;
- explicit config path;
- CLI overrides each TOML field;
- TOML-relative vs CLI-relative input paths;
- unknown keys;
- malformed TOML;
- wrong TOML types;
- invalid port, PDU, delay, timeout, format, host, AE titles;
- input missing/file/symlink/unreadable;
- Echo Run without input;
- help/version without config.

### 19.2 Catalog

Generate DICOM Part 10 fixtures with `pydicom` and test:

- arbitrary filename extensions;
- nested directories;
- non-DICOM bytes;
- malformed DICOM;
- missing each required UID/file-meta field;
- invalid UIDs;
- SOP dataset/file-meta mismatches;
- invalid/non-transfer Transfer Syntax UID;
- missing and malformed Instance Number;
- duplicate SOP Instance UID across directories;
- same Study UID across directories merges;
- deterministic Study, Series, and Instance ordering;
- permission/stat/read errors where portable;
- empty Catalog;
- no Pixel Data load during scan, using monkeypatch/spies rather than huge fixtures.

### 19.3 Transport unit tests

Use fake AE/Association objects to force branches that ProbeReceiver cannot naturally produce:

- association rejection;
- association abort;
- timeout/missing response;
- exact context rejection;
- mixed accepted/rejected contexts;
- C-STORE success;
- C-STORE warning;
- C-STORE failure;
- mid-Study association loss;
- full-file revalidation failure;
- cancellation before first send and between sends;
- release vs abort selection;
- context count 128 accepted by preflight;
- context count 129 rejected before AE creation.

### 19.4 Receiver integration tests

Use existing `ProbeReceiver` with temporary output:

1. Echo succeeds against Probe Lite.
2. One Study/one Instance creates one association and one stored file.
3. One Study/multiple Series/multiple Instances uses one association.
4. Multiple Studies use exactly one association per Study.
5. Study delay occurs `N-1` times; inject/patch wait to avoid slow tests.
6. Implicit VR Little Endian is preserved.
7. Explicit VR Little Endian is preserved.
8. Explicit VR Big Endian is preserved.
9. Same SOP Class with different transfer syntaxes in one Study sends through separate requested contexts on one association.
10. Receiver Calling AE whitelist accepts/rejects configured Calling AE correctly.
11. Received hierarchy remains `<Study>/<Series>/<SOP>.dcm`.
12. Sender logs contain UIDs/statuses but no patient fields.

Count associations via captured ProbeReceiver events or a narrow test-only observer; do not infer only from stored file count.

### 19.5 CLI and packaging

Test:

- `main()` exit `0`, `1`, `2`, `130` branches;
- text and JSON modes;
- final summary after partial failure;
- no final delay;
- handler restoration;
- module invocation;
- installed console script in packaging smoke test where CI supports it;
- wheel contains both packages.

## 20. Acceptance criteria

Implementation is complete only when all are true:

1. Zero args loads `./sender-lite.toml`; absence returns `2`.
2. CLI values override TOML values.
3. Echo mode is explicit and does not scan.
4. Normal mode scans recursively without following symlinks.
5. Catalog contains only strict, internally consistent DICOM files.
6. Duplicate SOP Instance UID copies are all excluded.
7. Ordering is deterministic and matches section 8.6.
8. One Study always maps to at most one association.
9. Multiple Studies map to separate associations.
10. Delay occurs between Studies only.
11. Exact original transfer syntax is requested and no transcoding occurs.
12. More than 128 requirements fails that Study without splitting.
13. Per-Instance failure continues while association remains usable.
14. Association loss fails unsent remainder and continues to next Study.
15. No retry occurs.
16. Full files are revalidated immediately before sending.
17. Logs are text or JSONL, stdout-only, one event per line, and contain no clinical metadata.
18. Final summary distinguishes success, warning, failure, and cancellation.
19. Exit codes match section 15.
20. Probe Lite behavior and tests remain unchanged.
21. Full Pytest/Ruff/format checks pass on CPython 3.13.
22. CI passes on Windows, macOS, and Linux.

## 21. Verification commands

Run from repository root using the existing environment/tooling:

```console
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
python -m zipfile -l dist/*.whl
```

Then perform a manual smoke test:

```console
probe-lite --output ./received --port 11112
sender-lite --input ./sample-dicom --host 127.0.0.1 --port 11112 --called-ae PROBE_LITE
sender-lite --echo --host 127.0.0.1 --port 11112 --called-ae PROBE_LITE
```

Expected:

- Probe Lite receives each Study in a separate association.
- Files appear under the existing Study/Series/SOP hierarchy.
- Sender waits only between Studies.
- Both processes report matching SOP Instance UIDs and statuses.

## 22. Risks and required mitigations

| Risk | Mitigation |
|---|---|
| Presentation-context leakage across Studies | fresh AE per Study |
| Mixed transfer syntaxes choose only one accepted syntax | one exact context per SOP/transfer pair |
| Study exceeds DICOM context limit | preflight count; fail without splitting |
| Catalog says one file, sender reads changed file | full-file identity revalidation before C-STORE |
| Duplicate SOP UID sends arbitrary copy | exclude every conflicting copy |
| Scan stalls on one bad file | per-file issue capture and continuation |
| Retry hides deterministic receiver defect | no retry |
| Cancellation leaves active association | explicit release/abort in `finally` paths |
| Real delay makes tests slow/flaky | cancellation Event wait; patch/inject in tests |
| Patient data leaks through logs | UID-only event contract; regression tests |
| Sender changes receiver behavior | separate package; full receiver regression suite |
| Existing dirty files overwritten | inspect and merge diffs before editing |

## 23. Handoff rules for implementing model

- Read `CONTEXT.md`, ADR-0027, this plan, `README.md`, `pyproject.toml`, and `docs/probe_lite/README.md` first.
- Inspect current git diff before editing.
- Follow Probe Lite patterns; do not refactor Probe Lite unless a failing Sender integration proves it necessary.
- Write tests alongside each phase, not after all production files.
- Keep associations and sends sequential.
- Never add implicit C-ECHO, retries, transcoding, persistent state, concurrency, or environment variables.
- Never choose one duplicate SOP file arbitrarily.
- Never split one Study across associations.
- Never suppress individual failure detail from the final result.
- Prefer deletion/simple local duplication over new shared abstractions.
- Stop and request clarification if implementation would violate an accepted criterion.

## 24. Library API checkpoints

Plan validated against current official documentation available on 2026-07-28:

- `pydicom` 3.0.2: `dcmread(..., stop_before_pixels=True, force=False)` and `UID.is_valid` / `UID.is_transfer_syntax`.
- `pynetdicom` 3.0.4: `AE.add_requested_context`, 128 requested-context limit, AE connection/ACSE/DIMSE/network timeouts, `AE.associate(..., ae_title=..., max_pdu=...)`, `Association.send_c_store`, and `Association.send_c_echo`.

Before implementation, re-check installed APIs if the lockfile resolves newer minor versions within the existing `<4.0` constraints. Do not redesign behavior solely because a helper API name changed.

## 25. Unresolved decisions

None. All product, transport, configuration, failure, lifecycle, and scope branches raised during the design interview are resolved above.
