# 01-product-vision.md

> **Project:** Lumora Probe  
> **Document:** Product Vision  
> **Status:** Architecture Baseline

---

# 1. Vision Statement

Lumora Probe aims to become the definitive engineering platform for observing, troubleshooting, and understanding DICOM communication.

The product combines protocol inspection, live monitoring, capture & replay, metadata exploration, lightweight image viewing, structured logging, and analytics into a single integrated workflow.

Unlike traditional DICOM viewers, Lumora Probe is designed primarily for engineers rather than clinicians.

---

# 2. Elevator Pitch

> **Lumora Probe is the "Wireshark + Chrome DevTools + Seq" for DICOM.**

It enables engineers to observe every stage of a DICOM exchange—from association negotiation through image display—and correlate protocol activity, timing, metadata, logs, and images to quickly identify interoperability and performance problems.

---

# 3. Problem Statement

Healthcare organizations frequently encounter issues such as:

- Slow C-STORE transfers
- Incomplete studies
- Missing instances
- Association failures
- Transfer syntax incompatibilities
- Vendor interoperability problems
- Large Enhanced MR datasets
- Timeouts and retries
- Storage bottlenecks

Existing tools typically expose only one part of the picture:

- Packet analyzers show network traffic.
- DICOM viewers show images.
- PACS logs show server activity.
- Vendor logs are proprietary.

Engineers must manually correlate information across multiple applications.

Lumora Probe brings these perspectives together into a single investigation workspace.

---

# 4. Product Goals

## Primary Goals

- Observe every DICOM association.
- Capture every important event.
- Make troubleshooting reproducible.
- Reduce root-cause analysis time.
- Provide a lightweight inspection viewer.
- Produce shareable engineering reports.
- Support vendor-specific diagnostics.

## Secondary Goals

- Educational tool for DICOM networking.
- Interoperability validation.
- Performance benchmarking.
- Protocol experimentation.

---

# 5. Product Philosophy

The product is built around **observability**, not storage.

The central object is not the image.

The central object is the **event**.

Every image, metadata object, DIMSE command, log entry, timing sample, and warning is represented as an event that can be inspected, replayed, searched, and correlated.

---

# 6. Design Principles

## Engineering First

Every screen should answer an engineering question.

## Explain Everything

The application should never simply say "Transfer Failed."

It should explain:

- what happened
- where it happened
- when it happened
- why it likely happened
- what to investigate next

## Progressive Disclosure

Novice users should see a simple interface.

Experts should be able to expand additional inspection panels without leaving the page.

## Fast Navigation

The application should support:

- keyboard shortcuts
- instant search
- lazy loading
- virtual scrolling

Large studies should remain responsive.

---

# 7. Product Pillars

## Observe

Live monitoring of DICOM activity.

## Capture

Persist complete engineering evidence.

## Inspect

Browse studies, series, instances, metadata, and events.

## Analyze

Automatically detect anomalies and summarize findings.

## Replay

Reproduce captured sessions for debugging.

## Report

Generate portable investigation reports.

## Extend

Support vendor plugins and custom analyzers.

---

# 8. Personas

## PACS Administrator

Needs to diagnose production issues quickly.

## Integration Engineer

Needs visibility into protocol behavior.

## Vendor Support Engineer

Needs reproducible evidence from customer sites.

## Software Developer

Needs deterministic replay and protocol inspection.

## QA Engineer

Needs automated validation and regression testing.

---

# 9. Success Metrics

The product should enable users to:

- identify failed associations quickly
- understand transfer bottlenecks
- locate missing instances
- inspect metadata without external tools
- replay production captures
- generate useful reports
- validate interoperability

---

# 10. Product Boundaries

Lumora Probe intentionally excludes:

- Clinical diagnosis
- Radiology reporting
- PACS archival
- RIS workflows
- Scheduling
- Billing
- Image interpretation

Those products already exist and are outside this project's mission.

---

# 11. Long-Term Vision

Over time, Lumora Probe may evolve into a broader observability platform supporting:

- DICOM
- DICOMweb
- HL7
- FHIR
- Vendor-specific protocols

The architecture should remain modular so additional healthcare interoperability protocols can be added without redesigning the core.

---

# 12. Guiding Principle

> Every feature must make it easier for an engineer to observe, understand, reproduce, or explain system behavior.

If a proposed feature does not support that goal, it likely belongs in another product rather than Lumora Probe.
