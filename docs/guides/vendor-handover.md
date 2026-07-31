# Vendor Handover Workflow

Lumora Probe handover artifacts support engineering investigation and vendor support. They
are not clinical records and are not a claim of standards conformance.

## 1. Preserve the source capture

1. Stop or promote the capture using the normal capture workflow.
2. Verify the capture package before export.
3. Keep the source capture unchanged. Every redacted or handover package receives a new
   capture ID and records `source_capture_id`.

## 2. Generate an investigation report

Reports can be generated as HTML, Markdown, or JSON. Each report records:

- observed conditions;
- rule-set version used for findings;
- evidence-linked findings and cited event sequences;
- decode timings;
- capture fidelity and provenance;
- partial-capture and client-asserted-event metadata.

Report generation is a background operation. The operation ID is the durable audit handle;
progress is published on the event bus and the operation is never resumed automatically
after a restart.

### PDF decision

HTML is the canonical printable report. PDF is produced with the operator's browser
**Print → Save as PDF** action. Lumora Probe does not add a server-side PDF dependency or
promise byte-identical PDF output across browsers. Markdown remains the portable text
format for tickets and source control.

## 3. Choose the safe handover format

Default handover export uses `fidelity: events`:

- event evidence is copied verbatim;
- protocol traces are copied when present;
- a whitelisted manifest metadata subset is retained;
- the `objects/` directory and pixel-bearing DICOM bytes are omitted.

The source package is verified before export and remains untouched. The exported manifest
records the source capture ID, source fidelity, export profile, and whether pixel data was
included.

## 4. Redact object-bearing evidence when required

Tag-level redaction applies a configurable profile to deep copies of DICOM objects and
writes the result as a new object-fidelity capture. Study, Series, and SOP Instance UIDs
are remapped consistently across objects and nested references so the investigation
hierarchy remains usable.

Redaction is deliberately limited. The output includes explicit warnings when content
cannot be verified, including:

- `BurnedInAnnotation` is not `NO`;
- Secondary Capture or Ultrasound SOP classes;
- screenshot-like modality/content;
- unrecognized private tags;
- free-text fields.

Warnings accompany the output manifest. Pixel content is not inspected or altered by the
tag-level operation.

## 5. Pixel-bearing export is deliberate

A pixel-bearing handover requires the explicit `pixel_bearing=True` option. The resulting
manifest marks the deliberate opt-in and retains the source provenance. Use this path only
after reviewing the capture, redaction warnings, and local information-governance policy.

The opt-in copies source object bytes; it does not apply tag-level redaction. To produce a
redacted object-bearing capture, run tag-level redaction first, review warnings, then use
that new capture as the source for any deliberate pixel-bearing handover.

## 6. Final checks before transfer

- Open and verify the exported `.lpcap` package.
- Confirm default event-fidelity exports contain no `objects/` entries.
- Confirm the source capture manifest, events, protocol traces, and object digests are
  unchanged.
- Review every redaction warning; do not treat an empty warning list as a claim that pixel
  content is clean.
- Include the report rule-set version and the operation/report IDs in the vendor ticket.

## Privacy posture

See [privacy-and-compliance-posture.md](privacy-and-compliance-posture.md) for ADR-0026 limits.
