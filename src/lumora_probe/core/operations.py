"""Durable operation audit records with in-memory execution state elsewhere."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .storage import StorageDatabases


class SQLiteOperationRegistry:
    """Persist operation history in the authoritative application database."""

    def __init__(self, databases: StorageDatabases) -> None:
        self.databases = databases

    async def get(self, operation_id: str) -> dict[str, Any] | None:
        rows = await self.databases.app.execute_read(
            "SELECT operation_id, job_type, parameters_json, state, started_at, completed_at, "
            "outcome, progress_json, interruption_reason FROM jobs WHERE operation_id = ?",
            (operation_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "operation_id": row["operation_id"],
            "job_type": row["job_type"],
            "parameters": json.loads(row["parameters_json"]),
            "state": row["state"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "outcome": row["outcome"],
            "progress": json.loads(row["progress_json"]),
            "interruption_reason": row["interruption_reason"],
        }

    async def start(
        self,
        *,
        operation_id: str,
        job_type: str,
        parameters: Mapping[str, Any],
        started_at: str,
    ) -> None:
        await self.databases.app.execute_write(
            "INSERT INTO jobs(operation_id, job_type, parameters_json, state, started_at, "
            "completed_at, outcome, progress_json, interruption_reason) "
            "VALUES (?, ?, ?, 'running', ?, NULL, NULL, '{}', NULL)",
            (operation_id, job_type, json.dumps(dict(parameters), sort_keys=True), started_at),
        )

    async def update_progress(self, operation_id: str, progress: Mapping[str, Any]) -> None:
        await self.databases.app.execute_write(
            "UPDATE jobs SET progress_json = ? WHERE operation_id = ?",
            (json.dumps(dict(progress), sort_keys=True), operation_id),
        )

    async def complete(self, operation_id: str, *, completed_at: str, outcome: str) -> None:
        await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'completed', completed_at = ?, outcome = ? "
            "WHERE operation_id = ?",
            (completed_at, outcome, operation_id),
        )

    async def mark_running_interrupted(self, *, reason: str) -> int:
        return await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'interrupted', interruption_reason = ? "
            "WHERE state = 'running'",
            (reason,),
        )


__all__: tuple[str, ...] = ()
