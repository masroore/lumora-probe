"""Tests for CI-enforced import contracts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT_IMPORTS = shutil.which("lint-imports") or str(Path(sys.executable).with_name("lint-imports"))


def test_all_import_contracts_are_kept() -> None:
    result = subprocess.run(
        [LINT_IMPORTS, "--no-cache"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Contracts: 7 kept, 0 broken." in result.stdout


def test_each_import_contract_fails_on_a_deliberate_violation() -> None:
    violations = (
        ("core_boundary", "core/domain.py", "from lumora_probe.associations import domain"),
        ("shared_boundary", "shared/domain.py", "from lumora_probe.captures import domain"),
        ("web_boundary", "associations/service.py", "from lumora_probe.web import api"),
        (
            "slice_public_api",
            "associations/service.py",
            "from lumora_probe.captures import domain",
        ),
        ("domain_purity", "associations/domain.py", "import fastapi"),
        ("plugin_boundary", "associations/service.py", "from lumora_probe.plugins import domain"),
    )

    for contract_name, relative_path, violation in violations:
        path = ROOT / "src" / "lumora_probe" / relative_path
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(f"{original}\n{violation}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    LINT_IMPORTS,
                    "--contract",
                    contract_name,
                    "--no-cache",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0, (
                f"{contract_name} accepted deliberate violation:\n{result.stdout}\n{result.stderr}"
            )
        finally:
            path.write_text(original, encoding="utf-8")
