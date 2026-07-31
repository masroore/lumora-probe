# ADR-0034: Neutral DICOM Infrastructure Shared by the Product Packages

- **Status:** Accepted
- **Date:** 2026-07-31
- **Scope:** `lumora_dicom_common`, Probe Lite, Sender Lite, and Lumora Probe
- **Supersedes:** Only the cross-product source-sharing prohibition to the narrow extent
  stated below; ADR-0028 remains authoritative for `lumora_lite_common`.

## Context

Probe Lite, Sender Lite, and Lumora Probe independently contain small pieces of DICOM
mechanical code. The overlap is limited to lexical identity handling and, potentially,
small `pynetdicom` compatibility details. Their workflows are not interchangeable:
receiving, sending, capture, event, storage, configuration, lifecycle, and result policies
belong to their respective products.

ADR-0028 intentionally made `lumora_lite_common` Lite-only and the Lite PRD describes the
Lite tools as independent from the parent application. Reusing that package from Lumora
Probe would violate that boundary and would also couple application policy to Lite policy.
A narrowly scoped neutral package is a safer alternative, but it requires an explicit ADR
gate before any production extraction.

## Decision

Create `src/lumora_dicom_common/` as neutral infrastructure, shipped in the existing
`lumora-probe` wheel. Do not create a separate distribution in this change. A separate
distribution remains a future option and requires its own decision.

### Dependency direction

`lumora_dicom_common` may import only the Python standard library during Stage 1. It must
not import `lumora_probe`, `probe_lite`, `sender_lite`, `lumora_lite_common`, the web
framework, database code, event-bus code, clock or ID code, `pydicom`, or `pynetdicom`.
Product packages may import neutral helpers, but no product package may import another
product package or `lumora_lite_common` from Lumora Probe.

### Staged scope

Stage 1 is limited to framework-free DICOM mechanics:

- UID lexical parsing and normalization from strings/scalars;
- AE-title ASCII/byte-length inspection from strings;
- defensive DIMSE status extraction, only where behavior-equivalent adapters are proven;
- stable constants only where their semantics are genuinely universal.

Stage 2 is optional. It may add a narrow, lazy `pynetdicom` compatibility/factory surface
only after a separately documented proof step demonstrates that the helper remains
mechanical. It must not own listener/SCU lifecycle, callbacks, async execution, storage,
logging, configuration policy, events, audit, cancellation, or retries.

### Product compatibility

Product adapters retain their own public names, validation policy, exception/result types,
logging, exit codes, defaults, and lifecycle. In particular:

- Lite retains `lumora_lite_common.uids` public functions and the
  `REASON_MISSING`, `REASON_MULTI_VALUED`, and `REASON_INVALID` categories.
- Lite does not reject whitespace or control ASCII AE titles merely because the neutral
  inspector reports them.
- Lumora Probe retains `AETitle`, `DICOMUID`, `DomainInvariantError`, and existing message
  families in `lumora_probe.shared.value_objects`.
- Port and PDU range validators remain product-owned. No neutral helper may merge the
  Lite ranges with Lumora Probe's non-privileged/listener ranges.
- Sender Lite retains its one-association-per-Study Batch rule and exit codes `0`, `1`,
  `2`, and `130`.

The neutral package supplies low-level results only. It is not a second application layer
and must not contain capture format, filesystem persistence, cataloging/batching, DICOM
listener lifecycle, sender/replay workflow, CLI parsing, logging, signals, event bus,
metrics, audit, or web code.

### Testing and architecture guard

Neutral code receives component-focused tests using strings/scalars and has no dependency
on product exception classes. Product adapters retain characterization tests before and
after migration. Tests must preserve current Lite and Lumora Probe behavior, including
byte/contract compatibility where existing tests assert it. Lumora Probe tests must not
sleep; injected clocks and IDs remain application-owned.

An import architecture contract must prevent neutral code from importing product packages,
Lite common, web/framework, database, event-bus, clock, and ID modules. The contract also
continues to enforce the existing product isolation and slice boundaries.

## Consequences

The repository gains one neutral package and one wheel package entry, but no second
application framework. Low-level DICOM identity mechanics can be tested once while each
product keeps its policy and observable contract. If a proposed extraction needs a product
callback, event, clock, ID generator, storage abstraction, lifecycle object, or async owner,
the extraction is rejected and the code remains product-owned.

ADR-0028 is not amended in place. This ADR links to it and to the Lite PRD, and creates a
narrow exception for `lumora_dicom_common` only. The Lite PRD's independence language is
updated to distinguish neutral mechanical infrastructure from product source sharing.
