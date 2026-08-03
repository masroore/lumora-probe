# User Workflows

Task-oriented guidance for common engineering personas. Deployment and backup procedures live
in the [operator guide](operator-guide.md).

## PACS administrator

1. Confirm Probe is reachable on loopback or through your approved reverse proxy.
2. Capture a failing association window (or promote from the ring buffer).
3. Open the workspace Study browser and note **partial** provenance when an instance appears
   in more than one capture.
4. Use Timeline (ordered by `sequence`) and Conditions/Findings separately: conditions are
   observed; findings are regenerable inferences.
5. Export a handover package with object-dropping (`events` fidelity) unless a controlled
   redaction workflow is required — see [vendor-handover.md](vendor-handover.md).

## Integration engineer

1. Validate AE titles, presentation contexts, and transfer syntaxes in Transfer Inspector.
2. Reproduce with **event replay** offline before any protocol replay against a real target.
3. Protocol replay defaults to dry-run; configure an explicit allowlisted target.
4. Treat client-asserted viewer events as quarantined — they must not drive timing or fidelity
   conclusions.
5. Generate HTML, Markdown, or JSON reports from a canonical Capture route; follow the
   operation link to inspect provenance and preview/download the artifact.

## Operator

1. Use Settings to inspect effective values and their source before changing runtime policy.
2. Environment- and file-owned values are locked; startup-only changes require a restart.
3. Use Plugins to inspect compatibility, health, failures, and declared capabilities.
4. Plugin capabilities are disclosure only. Plugins are trusted in-process code, and
   enable/disable changes take effect after restart. Installation is deliberately CLI-only.

## QA engineer

1. Prefer synthetic DICOM fixtures under the project UID namespace.
2. Assert capture integrity (gap-free `sequence`, digests) before analysis claims.
3. Re-run analysis after rule-set changes; findings regenerate under `analysis/`.
4. Use Search for incremental study/series/instance/event/log lookups on large result sets.

## Vendor support

1. Request an events-fidelity handover first; avoid unnecessary pixel-bearing objects.
2. Read report warnings about burned-in pixels, private tags, and free text honestly.
3. Do not interpret Probe redaction as de-identification or PS3.15 compliance — see
   [privacy-and-compliance-posture.md](privacy-and-compliance-posture.md).
