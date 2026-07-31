# DICOM interoperability suite

## Purpose

Exercise Lumora's DICOM relay against real DCMTK, dcm4che, and Orthanc implementations.
The suite is opt-in and non-gating. CI runs it only from the scheduled/manual workflow;
the normal push and pull-request gate never starts external implementations.

## Scope

Implemented scenarios:

- **DCMTK 3.6.8:** positive C-ECHO and C-STORE through the Lumora relay to the
  DCMTK SCP using the committed synthetic Explicit VR Little Endian fixture, plus
  negative calling-AE rejection followed by a successful association proving relay recovery.

The dcm4che, Orthanc, and full transfer-syntax matrix scenarios belong to subsequent
Phase 20 tasks.

## Prerequisites

- Docker with Compose support.
- Images available from the configured registries.
- Host permits an intentionally non-loopback test relay. Setting
  `LUMORA_INTEROP=1` is the explicit acknowledgment for this isolated suite.
- On platforms where containers use a different hostname for the host, set
  `LUMORA_INTEROP_HOST`; the default is `host.docker.internal`.

## Run

```console
docker compose -f tests/interop/docker-compose.yml --profile interop up -d --wait dcmtk
LUMORA_INTEROP=1 uv run pytest tests/interop/test_dcmtk.py -m interop -q
docker compose -f tests/interop/docker-compose.yml --profile interop down -v
```

## Expected outcomes

All enabled implementation scenarios execute; no interop test is skipped. Positive cases traverse the Lumora relay and receive DICOM success responses. Negative cases
fail for the asserted protocol reason and leave the Lumora relay able to accept the next valid
association.

## Maintenance

Keep implementation images immutable by digest. Update the documented implementation
version and rerun every scenario when changing a digest. Fixtures remain synthetic-only
and must be regenerated through `scripts/generate_fixtures.py`; never add clinical or
"de-identified" patient data. Publish Phase 20 matrix results separately, including any
failures and triage.
