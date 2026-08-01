# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 18 large synthetic study projection workload (2,000 instances)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases, rebuild_study_projection
from lumora_probe.studies.repository import StudyProjectionRepository
from lumora_probe.studies.service import StudyBrowserService
from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore

UID_ROOT = "1.2.826.0.1.3680043.10.543.18"
CAPTURE_ID = "018f0d4e-7b6a-7000-8000-000000001800"
INSTANCE_COUNT = 2000


def _seed_large_study(tmp_path: Path) -> StudyProjectionRepository:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    created_at = datetime(2026, 7, 31, tzinfo=UTC).isoformat()
    study_uid = f"{UID_ROOT}.1"
    series_uid = f"{UID_ROOT}.1.1"

    with databases.index.write_transaction() as connection:
        connection.execute(
            "INSERT INTO captures(capture_id, path, source_root, format_version, created_at, "
            "completed_at, state, fidelity, partial, promoted_from_buffer, interruption_reason, "
            "manifest_sha256, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                CAPTURE_ID,
                str(paths.captures / CAPTURE_ID),
                str(paths.captures),
                1,
                created_at,
                created_at,
                "completed",
                "objects",
                0,
                0,
                None,
                "a" * 64,
                created_at,
            ),
        )
        rows = [
            (
                CAPTURE_ID,
                study_uid,
                series_uid,
                f"{UID_ROOT}.1.1.{index}",
                f"{index:064x}",
                f"objects/{index:064x}",
                "1.2.840.10008.1.2.1",
                None,
                None,
                created_at,
            )
            for index in range(INSTANCE_COUNT)
        ]
        connection.executemany(
            "INSERT INTO instances(capture_id, study_uid, series_uid, sop_instance_uid, "
            "object_digest, object_path, transfer_syntax_uid, rows, columns, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        rebuild_study_projection(connection)

    return StudyProjectionRepository(databases, capture_roots=(paths.captures,))


@pytest.mark.component
@pytest.mark.slow
@pytest.mark.asyncio
async def test_large_study_browser_handles_two_thousand_instances(tmp_path: Path) -> None:
    started = time.monotonic()
    repository = _seed_large_study(tmp_path)
    study_uid = f"{UID_ROOT}.1"
    instances = await repository.list_instances(study_uid=study_uid)
    assert len(instances) == INSTANCE_COUNT

    browser = StudyBrowserService.browser(study_uid, instances)
    assert browser["study_uid"] == study_uid
    assert browser["partial"] is False
    assert len(browser["instances"]) == INSTANCE_COUNT
    # Projection browse must not require pixel decode; rows/columns stay unset.
    assert all(instance.rows is None and instance.columns is None for instance in instances)

    store = InMemoryResourceStore(
        {
            "studies": {
                study_uid: {
                    "study_uid": study_uid,
                    "instance_count": INSTANCE_COUNT,
                    "partial": False,
                }
            },
            "instances": {
                instance.sop_instance_uid: {
                    "id": instance.sop_instance_uid,
                    "study_uid": instance.study_uid,
                    "series_uid": instance.series_uid,
                    "sop_instance_uid": instance.sop_instance_uid,
                    "capture_id": instance.capture_id,
                }
                for instance in instances
            },
        }
    )

    class Provider:
        async def get_study_browser(self, requested: str):
            if requested != study_uid:
                return None
            return browser

    application = create_app(projection_store=store, study_browser_provider=Provider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get(f"/api/v1/studies/{study_uid}/browser")
        list_response = await client.get(
            "/api/v1/instances",
            params={"page": 1, "page_size": 50, "filter": f"study_uid:{study_uid}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["present_in_capture_count"] == 1
    assert len(payload["instances"]) == INSTANCE_COUNT
    assert list_response.status_code == 200
    assert list_response.json()["total"] == INSTANCE_COUNT
    print(
        {
            "dimension": "large_study",
            "instance_count": INSTANCE_COUNT,
            "elapsed_seconds": time.monotonic() - started,
        }
    )
