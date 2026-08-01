# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Trusted plugin loading and public extension contracts."""

from .api import build_plugin_manager, hookimpl, hookspec
from .bundled_rules import bundled_plugin, bundled_rules
from .contracts import PLUGIN_SDK_MAJOR, PLUGIN_SDK_VERSION
from .repository import PluginRepository
from .service import PluginService

__all__ = [
    "PLUGIN_SDK_MAJOR",
    "PLUGIN_SDK_VERSION",
    "PluginRepository",
    "PluginService",
    "build_plugin_manager",
    "bundled_plugin",
    "bundled_rules",
    "hookimpl",
    "hookspec",
]
