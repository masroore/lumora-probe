# Synthetic DICOM fixtures

Generated only by `scripts/generate_fixtures.py` with pydicom. Files contain synthetic
identifiers and pixels; no patient or de-identified clinical data is permitted.

Regenerate:

```console
rm -rf tests/fixtures/dicom/synthetic_study
uv run python scripts/generate_fixtures.py tests/fixtures/dicom/synthetic_study
```
