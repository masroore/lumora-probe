# Known Limitations

Lumora Probe is an engineering observability and troubleshooting platform. It is not a
PACS, RIS, EMR, diagnostic workstation, clinical archive, or de-identification service.

## DICOM protocol scope

- **C-MOVE sub-operations are out of band.** Probe records the request and progress
  responses, but the PACS sends C-STORE sub-operations directly to the configured destination
  AE. To observe those objects, configure the destination AE to point at Probe or use C-GET.
- **Transfer-syntax coverage depends on the peer and installed codecs.** The release matrix
  covers Explicit VR Little Endian, RLE Lossless, JPEG Lossless SV1, JPEG Baseline, and
  JPEG-LS Lossless. Other syntaxes are not claimed unless present in the published matrix.
- **No PS3.15 conformance claim.** Probe does not provide a DICOM PS3.15 de-identification
  profile or promise removal of burned-in or private identifying data.
- **PCAP import and remote collectors are not release features.** They remain deferred
  roadmap work, not hidden capabilities.

## Security and trust

- **No built-in authentication or RBAC.** Deploy behind an authenticated reverse proxy or
  another trusted network boundary. The application exposure gate still requires an explicit
  non-loopback acknowledgment.
- **Plugins are trusted in-process code.** Plugin manifests disclose capabilities but do not
  sandbox or enforce them. Install only reviewed plugin code.
- **No in-application TLS termination.** Use the documented reverse-proxy boundary for TLS.

## Release verification

- External interoperability is an opt-in scheduled suite and is intentionally outside the
  default push/pull-request gate. The final pinned-container result is 15 passed, 0 failed in
  hosted CI run `30716744830`, job `91413482214`, at release-evidence SHA `44edd6e` (source implementation `c445bec`). Results are
  published in `docs/planning/phase-20-interop-results.md`.
- Performance dimensions not ratified as release budgets remain measured evidence rather than
  newly invented gates; see `docs/planning/phase-18-performance-report.md`.

## Release-closure evidence limits

The checked-in structural performance suite proves bounded query and ring-persistence behavior;
it does not claim the ratified p95 budgets on every machine. Reference timing evidence is limited
to the documented local macOS/SQLite-WAL host. Network filesystems remain outside the supported
SQLite deployment. Installed wheel/sdist smoke passed in the six-job Linux/macOS/Windows CI matrix in hosted run
`30716744830`.
