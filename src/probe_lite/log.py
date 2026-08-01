# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Stdout-only text and JSONL event logging."""

from __future__ import annotations

from typing import ClassVar

from lumora_lite_common.logging import EventLogger


class ProbeLogger(EventLogger):
    """Probe Lite event labels on the shared logger engine (see ADR-0028)."""

    TEXT_LABELS: ClassVar[dict[str, str]] = {
        "startup": "Startup",
        "association_requested": "Association requested",
        "association_accepted": "Association accepted",
        "association_rejected": "Association rejected",
        "association_released": "Association released",
        "association_aborted": "Association aborted",
        "instance_received": "Instance received",
        "instance_store_failed": "Instance store failed",
        "c_echo_received": "C-ECHO received",
        "shutdown": "Shutdown",
    }
