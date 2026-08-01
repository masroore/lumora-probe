# Phase 20 Interoperability Results

**Execution date:** 2026-08-01  
**Suite:** scheduled/manual, opt-in (`LUMORA_INTEROP=1`)  
**Result:** 15 passed, 0 failed

## Execution

```console
docker compose -f tests/interop/docker-compose.yml --profile interop up -d --wait \\
  dcmtk dcm4che orthanc
LUMORA_INTEROP=1 uv run pytest -m interop tests/interop -q -ra
docker compose -f tests/interop/docker-compose.yml --profile interop down -v
```

The default quality gate does not start these containers. Without `LUMORA_INTEROP=1`,
the implementation-facing modules are skipped by design. The final hosted run used release-evidence
SHA `44edd6ecb78c67f7ddd8c6eb845ad712b1769590` (source implementation `c445bec`), CI run `30716744830`, job `91413482214`, and
reported `15 passed, 556 deselected in 20.86s`.

## Pinned implementations

| Implementation | Version | Image digest | Role |
|---|---:|---|---|
| DCMTK | 3.6.8 | `sha256:f66d95cad6bf0f361ddd6c46bf7c6563319b8d7bf284ad3d345b8d7ee04a2ab8` | C-ECHO/C-STORE SCU, SCP, synthetic transfer-syntax encoder |
| dcm4che | 5.33.1 | `sha256:c8fbede4a6cf6047370ad21ce12fcc6be7ab013ff4996f1d032eb55239f870ed` | C-ECHO/C-STORE SCU with exact transfer-syntax proposal |
| Orthanc | 24.5.1 | `sha256:a1b7fb6d1de31693949165c64b88fa35fae51fdeb9732fcef69cd75daea7ff9d` | DICOM SCP for relay and transfer-syntax matrix |

## Results matrix

| Implementation path | Positive C-ECHO | Positive C-STORE | Negative calling-AE/recovery | Transfer syntax matrix |
|---|---:|---:|---:|---:|
| DCMTK through Lumora to DCMTK | 1 pass | 1 pass | 1 pass | baseline covered |
| dcm4che through Lumora to DCMTK | 1 pass | 1 pass | 1 pass | exact syntax sender |
| DCMTK through Lumora to Orthanc | 1 pass | 1 pass | 1 pass | matrix upstream |
| dcm4che through Lumora to Orthanc | — | — | — | 5 pass |

## Transfer-syntax coverage

The matrix generated deterministic synthetic objects and sent them through Lumora to
Orthanc with one exact proposed transfer syntax per association:

- Explicit VR Little Endian;
- RLE Lossless;
- JPEG Lossless SV1;
- JPEG Baseline;
- JPEG-LS Lossless.

The matrix asserted the encoded file metadata before transmission and the successful
C-STORE response after relay forwarding. JPEG 2000, MPEG, HEVC, and other syntaxes that
lack an encoder in the pinned DCMTK image remain outside this matrix and are not claimed as
covered.

## Failure triage

| Observation | Disposition |
|---|---|
| Existing `dcmtk/dcmtk:3.6.8` reference could not be resolved | Replaced with a working DCMTK 3.6.8 image pinned by digest. Resolved. |
| Existing `dcm4che/dcm4che-tools:5.34.1` reference could not be resolved | Replaced with dcm4che 5.33.1 pinned by digest. Resolved and documented. |
| Compressed transfer syntax forwarding to the DCMTK `storescp` path returned `A700` during matrix bring-up | Reproduced only for that peer/path. Exact compressed negotiation and forwarding pass against Orthanc; the DCMTK baseline suite remains green. Retained as a peer-specific follow-up rather than hidden. |
| Orthanc DICOM port was initially published broadly by the skeleton | Restricted to `127.0.0.1:4242`; no broader host exposure is needed for the suite. Resolved. |

No failure was omitted from the executed final suite. The scheduled job remains
non-gating per ADR-0022, but this final-SHA run is the retained result artifact for release review.

## Maintenance

Change an image only by updating its version, digest, and this report together. Rerun the
full command above after any image, fixture, relay, or transfer-syntax change. Keep
fixtures synthetic-only and retain failure output when a scheduled run is not green.
