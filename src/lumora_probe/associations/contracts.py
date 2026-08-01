# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Public contracts for the DICOM association and relay slice."""

from __future__ import annotations

from typing import Protocol

from . import network as _network
from . import relay as _relay

AssociationAuditRecord = _network.AssociationAuditRecord
AssociationAuditSink = _network.AssociationAuditSink
AssociationClock = _network.AssociationClock
AssociationEventIngress = _network.AssociationEventIngress
AssociationIdGenerator = _network.AssociationIdGenerator
AssociationLogger = _network.AssociationLogger
CStoreSink = _network.CStoreSink
DICOMEchoResult = _network.DICOMEchoResult
DICOMListenerConfig = _network.DICOMListenerConfig
DICOMSCUConfig = _network.DICOMSCUConfig
DICOMStoreResult = _network.DICOMStoreResult
PDUTraceSink = _network.PDUTraceSink
PDUTraceRecord = _relay.PDUTraceRecord
RelayConfig = _relay.RelayConfig
RelayMode = _relay.RelayMode


class DICOMDatasetSender(Protocol):
    """Async contract for sending one captured DICOM dataset as an SCU."""

    async def send_dataset(self, data: bytes, *, transfer_syntax: str) -> DICOMStoreResult:
        """Send one encoded dataset and return its C-STORE result."""
        ...


__all__: tuple[str, ...] = ()
