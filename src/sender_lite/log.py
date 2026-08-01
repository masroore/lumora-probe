# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Stdout-only text and JSONL event logging for Sender Lite.

The logging engine lives in `lumora_lite_common.logging` (see ADR-0028);
this module keeps the Sender Lite event labels and the `SenderLogger`
name. `ProbeLogger` is the sibling subclass in `probe_lite.log`.

PHI rule (section 14.3): never log Patient Name, Patient ID, accession
number, dates of birth, Study/Series descriptions, free-text dataset
values, or full dataset dumps. UIDs and source paths are allowed for
engineering correlation. Source paths may themselves contain sensitive
text.
"""

from __future__ import annotations

from typing import ClassVar

from lumora_lite_common.logging import EventLogger


class SenderLogger(EventLogger):
    """Sender Lite event labels on the shared logger engine (see ADR-0028)."""

    TEXT_LABELS: ClassVar[dict[str, str]] = {
        "configuration_resolved": "Configuration resolved",
        "scan_started": "Scan started",
        "file_skipped": "File skipped",
        "catalog_conflict": "Catalog conflict",
        "scan_completed": "Scan completed",
        "study_started": "Study started",
        "association_accepted": "Association accepted",
        "association_rejected": "Association rejected",
        "association_aborted": "Association aborted",
        "association_negotiation": "Association negotiation",
        "presentation_context_rejected": "Presentation context rejected",
        "instance_sent": "Instance sent",
        "instance_warning": "Instance warning",
        "instance_failed": "Instance failed",
        "study_completed": "Study completed",
        "study_delay_started": "Study delay started",
        "echo_completed": "Echo completed",
        "cancellation_requested": "Cancellation requested",
        "run_completed": "Run completed",
        "run_failed": "Run failed",
    }
