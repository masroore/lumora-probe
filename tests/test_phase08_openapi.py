# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the generated Phase 08 OpenAPI artifact."""

from __future__ import annotations

import json
from pathlib import Path

from lumora_probe.web.api import API_PREFIX, create_app

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs/generated/openapi-v1.json"


def test_openapi_artifact_matches_application_schema() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    schema = create_app().openapi()

    assert artifact == schema
    assert artifact["info"]["title"] == "Lumora Probe"
    assert API_PREFIX not in artifact["paths"]
