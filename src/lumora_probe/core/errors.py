# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Structured errors shared by Lumora Probe infrastructure components."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LumoraError(Exception):
    """An operator-facing error with context and an actionable remediation."""

    code: str
    message: str
    remediation: str
    context: Mapping[str, Any] = field(default_factory=lambda: dict[str, Any]())

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
            "context": dict(self.context),
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} Remediation: {self.remediation}"


class ConfigurationError(LumoraError):
    """Startup or runtime configuration is invalid."""


class SettingLockedError(ConfigurationError):
    """A setting cannot be changed because a higher-precedence source owns it."""


class RestartRequiredError(ConfigurationError):
    """A startup-only setting was changed while the process is running."""


class PathSecurityError(LumoraError):
    """A user-derived path is invalid or escapes an allowed root."""


class NetworkFilesystemError(LumoraError):
    """SQLite data was requested on a network filesystem."""


class VersionMismatchError(LumoraError):
    """A data directory was created by a newer application version."""


class NetworkExposureError(LumoraError):
    """A non-loopback bind lacks the explicit unauthenticated-network acknowledgment."""


class LifecycleError(LumoraError):
    """A service lifecycle transition failed."""
