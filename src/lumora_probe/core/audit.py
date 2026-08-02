# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Append-only application audit records and category coverage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .storage import SQLiteDatabase


class AuditCategory(StrEnum):
    LOGIN = "Login"
    LOGOUT = "Logout"
    PERMISSION_CHANGE = "PermissionChanged"
    CONFIGURATION_CHANGE = "ConfigurationChanged"
    PLUGIN_INSTALLATION = "PluginInstalled"
    ADMINISTRATIVE_ACTION = "AdministrativeAction"
    SECURITY_FAILURE = "SecurityFailure"


@dataclass(frozen=True, slots=True)
class AuditRecord:
    audit_id: int
    event_type: str
    entity_type: str
    entity_id: str | None
    occurred_at: str
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
        }


class AuditLog:
    """Use the existing ``app.db`` audit table without changing its schema."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    async def append(
        self,
        category: AuditCategory | str,
        *,
        entity_type: str,
        entity_id: str | None = None,
        occurred_at: datetime,
        payload: Mapping[str, Any] = {},
    ) -> None:
        await self.database.execute_write(
            "INSERT INTO audit_log(event_type, entity_type, entity_id, occurred_at, payload_json) VALUES (?, ?, ?, ?, ?)",
            (
                str(category),
                entity_type,
                entity_id,
                occurred_at.isoformat(),
                json.dumps(dict(payload), sort_keys=True, default=str),
            ),
        )

    def append_sync(
        self,
        category: AuditCategory | str,
        *,
        entity_type: str,
        entity_id: str | None = None,
        occurred_at: datetime,
        payload: Mapping[str, Any] = {},
    ) -> None:
        """Synchronous composition-root helper for sync management adapters."""
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO audit_log(event_type, entity_type, entity_id, occurred_at, payload_json) VALUES (?, ?, ?, ?, ?)",
                (
                    str(category),
                    entity_type,
                    entity_id,
                    occurred_at.isoformat(),
                    json.dumps(dict(payload), sort_keys=True, default=str),
                ),
            )

    async def list(
        self,
        *,
        category: AuditCategory | str | None = None,
        limit: int = 100,
        cursor: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> tuple[AuditRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("audit page limit must be between 1 and 100")
        if cursor is not None and (type(cursor) is not int or cursor < 0):
            raise ValueError("audit page cursor must be a non-negative integer")
        clauses: list[str] = []
        parameters: list[Any] = []
        if category is not None:
            if str(category) == AuditCategory.ADMINISTRATIVE_ACTION.value:
                clauses.append("event_type IN (?, ?, ?)")
                parameters.extend(
                    [
                        AuditCategory.ADMINISTRATIVE_ACTION.value,
                        "CaptureDeleted",
                        "ProtocolReplayAudit",
                    ]
                )
            else:
                clauses.append("event_type = ?")
                parameters.append(str(category))
        if entity_type is not None:
            clauses.append("entity_type = ?")
            parameters.append(entity_type)
        if entity_id is not None:
            clauses.append("entity_id = ?")
            parameters.append(entity_id)
        if cursor is not None:
            clauses.append("audit_id < ?")
            parameters.append(cursor)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await self.database.execute_read(
            "SELECT audit_id, event_type, entity_type, entity_id, occurred_at, payload_json "
            f"FROM audit_log {where} ORDER BY audit_id DESC LIMIT ?",
            (*parameters, limit),
        )
        return tuple(
            AuditRecord(
                int(row["audit_id"]),
                str(row["event_type"]),
                str(row["entity_type"]),
                row["entity_id"],
                str(row["occurred_at"]),
                json.loads(str(row["payload_json"])),
            )
            for row in rows
        )


AUDIT_CATEGORY_COVERAGE: Mapping[AuditCategory, str] = {
    AuditCategory.LOGIN: "Deferred until authentication ADR; no fake login records.",
    AuditCategory.LOGOUT: "Deferred until authentication ADR; no fake logout records.",
    AuditCategory.PERMISSION_CHANGE: "Deferred until authorization/RBAC ADR.",
    AuditCategory.CONFIGURATION_CHANGE: "Runtime configuration mutations.",
    AuditCategory.PLUGIN_INSTALLATION: "CLI plugin installation and validation.",
    AuditCategory.ADMINISTRATIVE_ACTION: "Deletes, exports, replay, retention, enable/disable.",
    AuditCategory.SECURITY_FAILURE: "Exposure refusals, containment failures, and denials.",
}


__all__ = ["AUDIT_CATEGORY_COVERAGE", "AuditCategory", "AuditLog", "AuditRecord"]
