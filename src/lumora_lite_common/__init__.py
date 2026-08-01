# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Shared helpers for the Lumora Lite tools (Probe Lite and Sender Lite).

This package holds the genuinely duplicated behaviour between the two Lite
tools: the event-logger engine, portable signal install/restore, config leaf
validators, and DICOM UID validation. It is internal to the Lite codebase and
does not share code with the parent ``lumora/`` project. See ADR-0028.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config_validators import (
    MAX_AE_BYTES,
    MAX_MAX_PDU,
    MAX_PORT,
    MIN_AE_BYTES,
    MIN_MAX_PDU,
    MIN_PORT,
    validate_ae_title,
    validate_log_format,
    validate_max_pdu,
    validate_port,
)
from .logging import EventLogger
from .signals import install_signal_handlers, restore_signal_handlers
from .uids import (
    REASON_INVALID,
    REASON_MISSING,
    REASON_MULTI_VALUED,
    is_valid_uid,
    safe_uid,
    validate_uid,
)

__all__ = [
    "MAX_AE_BYTES",
    "MAX_MAX_PDU",
    "MAX_PORT",
    "MIN_AE_BYTES",
    "MIN_MAX_PDU",
    "MIN_PORT",
    "REASON_INVALID",
    "REASON_MISSING",
    "REASON_MULTI_VALUED",
    "EventLogger",
    "__version__",
    "install_signal_handlers",
    "is_valid_uid",
    "restore_signal_handlers",
    "safe_uid",
    "validate_ae_title",
    "validate_log_format",
    "validate_max_pdu",
    "validate_port",
    "validate_uid",
]
