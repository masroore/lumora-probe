# Phase 06 Capture Format Specification

**Status:** Implemented
**Format version:** `1`
**Working form:** self-contained directory
**Interchange form:** `.lpcap` ZIP archive using deflate

## Layout

```text
<captures-root>/<uuidv7>/
  manifest.json
  events.jsonl
  pdus.jsonl
  objects/<sha256>
  logs/                 # reserved for capture-local logs
  analysis/             # reserved for regenerable analysis output
```

The capture directory is the source of truth. `index.db` stores only projections and
can be deleted and rebuilt. The directory must contain `manifest.json`; `events.jsonl`,
`pdus.jsonl`, and `objects/` are created as needed by the evidence fidelity.

## Manifest

`manifest.json` is UTF-8 JSON with sorted keys and compact separators. Required fields:

- `format_version`: currently `1`; readers refuse newer versions.
- `capture_id`: UUIDv7 capture identity.
- `created_at`, optional `completed_at`: timezone-aware timestamps.
- `fidelity`: `events`, `protocol`, `wire`, or `objects`.
- `state`: lifecycle state at sealing time (`completed` or `interrupted`).
- `source`: provenance label (`live` by default).
- `partial`, `promoted_from_buffer`, `incomplete_aggregates`.
- `client_asserted_event_count`.
- optional `clock_anchor` with wall-clock and monotonic samples.
- `objects`: content-addressed object inventory, including DICOM hierarchy and digest.

Unknown manifest fields are retained when read and written. This permits forward fields
to survive a read/write cycle without making the reader claim support for a newer format.

## JSONL records

`events.jsonl` and `pdus.jsonl` are append-only. Each record is one UTF-8 JSON value and
ends with a newline. The writer accepts pre-serialized bytes so event envelopes can be
persisted verbatim. The default durability policy flushes and `fsync`s each record;
`flush` and `never` are explicit opt-down policies for controlled workloads.

Events are canonical envelopes and belong on the event path. PDU records are minimal
protocol traces and do not become event-bus envelopes.

A crash may leave a torn trailing line. Recovery must discard only that incomplete final
line; complete preceding records remain valid.

## Content-addressed objects

Object filenames are lowercase SHA-256 digests of their exact bytes. Writes use a
same-directory temporary file, `fsync`, and atomic replacement. Re-sending identical
bytes returns the existing digest without a second object. Manifest object entries provide
DICOM provenance and permit index rebuilds without reparsing pixels.

Integrity verification reports missing, changed, and unexpected object files. Missing or
changed expected objects fail verification; unexpected files are reported for operator
inspection.

## `.lpcap` archives

Packing writes all regular files under the capture directory in deterministic path order.
Symlinks are rejected. Unpacking rejects absolute paths, `..` traversal, and symlink
entries before writing any member. The archive is an interchange form; unpacked
captures remain the working form.

## Compatibility

The current reader supports format version `1`. A newer version is refused with an
operator-facing remediation rather than being partially interpreted. A future format
must add an explicit compatibility rule and versioned tests before changing the reader.
