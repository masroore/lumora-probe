# DICOM interoperability suite

The suite is opt-in and non-gating. CI runs it on the scheduled/manual workflow only;
the normal push and pull-request gate never starts external implementations.

The compose file provides pinned DCMTK, dcm4che, and Orthanc containers. Add concrete
SCU/SCP scenarios here as each implementation-facing contract is introduced.

Run locally:

```console
docker compose -f tests/interop/docker-compose.yml --profile interop up -d
LUMORA_INTEROP=1 uv run pytest -m interop -q
docker compose -f tests/interop/docker-compose.yml --profile interop down -v
```
