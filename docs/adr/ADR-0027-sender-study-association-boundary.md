# ADR-0027: One Exact-Fidelity Association per Sender Study

- **Status:** Accepted
- **Date:** 2026-07-28
- **Scope:** Sender Lite only

## Context

Sender Lite exists to exercise DICOM receivers with reproducible Study-level traffic. Reusing one association across Studies would blur batch boundaries; opening one association per Instance would not resemble a normal Study send. Transcoding would also make the sender alter the evidence it is meant to submit.

## Decision

Each Study Batch uses exactly one DICOM association. Sender Lite requests one presentation context for every unique `(SOP Class UID, Transfer Syntax UID)` pair in that Study, sends accepted Instances sequentially without transcoding, then releases the association. It waits the configured delay before the next Study. A Study requiring more than 128 presentation contexts fails preflight and is never split across associations.

## Consequences

Association lifecycle and logs align one-to-one with Study Batches. Mixed transfer syntaxes remain byte-semantically faithful, but receiver context rejection becomes an Instance failure and unusually heterogeneous Studies may be unsendable without changing this decision.
