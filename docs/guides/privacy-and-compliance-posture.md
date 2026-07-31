# Privacy and Compliance Posture

This document states Lumora Probe’s honest limits under ADR-0026 and Security Architecture §17.
It is **not** a compliance certification.

## What captures may contain

Capture packages may contain Protected Health Information (PHI) and other sensitive DICOM
content, including pixel data, private tags, free text, and structured reports.

## Redaction is not de-identification

- “Redact” means **partial** tag-level redaction or object-dropping handover preparation.
- Lumora Probe does **not** claim anonymization, de-identification, or **PS3.15** conformance.
- Object-dropping / events-fidelity export is the **safe default** for vendor handover.

## Residual risks after redaction

Even after tag redaction, residual disclosure risks remain, including:

- private tags not covered by the profile;
- free-text and structured content;
- burned-in pixel PHI;
- identifiers reconstituted across residual fields.

## Deployment responsibilities

Encryption in transit/at rest, access control, retention, lawful basis, breach response, and
jurisdiction-specific obligations (including HIPAA/GDPR operational controls) are
**deployment and organizational responsibilities**. Probe’s loopback default and reverse-proxy
TLS guidance do not transfer those duties into the product.

## Cross-links

- [vendor-handover.md](vendor-handover.md)
- [operator-guide.md](operator-guide.md)
- ADR-0026
