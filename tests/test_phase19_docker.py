# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 19 Docker image contract checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_dockerfile_has_non_root_single_volume_contract() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.13-slim" in dockerfile
    assert "USER lumora" in dockerfile
    assert 'VOLUME ["/var/lib/lumora"]' in dockerfile
    assert "LUMORA_DATA_DIR=/var/lib/lumora" in dockerfile
    assert "LUMORA_ALLOW_UNAUTHENTICATED_NETWORK=true" in dockerfile
    assert '"--trust-network", "--host", "0.0.0.0"' in dockerfile
    assert "npm" not in dockerfile.lower()
    assert "node" not in dockerfile.lower()


def test_docker_context_excludes_development_only_inputs() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "node_modules" in dockerignore
    assert ".venv" in dockerignore
    assert "assets/source" in dockerignore
    assert "tests" in dockerignore
