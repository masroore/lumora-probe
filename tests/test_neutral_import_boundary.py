"""Architecture guard for the neutral DICOM package."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

NEUTRAL_PACKAGE = Path(__file__).parents[1] / "src" / "lumora_dicom_common"
FORBIDDEN_ROOTS = {
    "lumora_probe",
    "probe_lite",
    "sender_lite",
    "lumora_lite_common",
    "fastapi",
    "sqlalchemy",
    "jinja2",
    "pydicom",
    "pynetdicom",
    "time",
    "uuid",
}


def test_neutral_package_has_no_product_or_runtime_imports() -> None:
    if not NEUTRAL_PACKAGE.exists():
        pytest.skip("neutral package is created in the next implementation phase")

    violations: list[str] = []
    for path in sorted(NEUTRAL_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            imported = node.module if isinstance(node, ast.ImportFrom) else None
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif imported is not None:
                names = [imported]
            else:
                continue
            for name in names:
                root = name.split(".", 1)[0]
                if root in FORBIDDEN_ROOTS:
                    violations.append(f"{path.name}: {name}")

    assert violations == []
