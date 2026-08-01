# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the narrow neutral pynetdicom compatibility surface."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pynetdicom
import pynetdicom._globals as pynetdicom_globals
import pytest

from lumora_dicom_common.pynetdicom_runtime import (
    add_supported_contexts,
    configure_receive_runtime,
    load_all_transfer_syntaxes,
)


def test_load_all_transfer_syntaxes_uses_public_symbol() -> None:
    assert load_all_transfer_syntaxes() is pynetdicom.ALL_TRANSFER_SYNTAXES


def test_load_all_transfer_syntaxes_falls_back_to_private_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public = pynetdicom.ALL_TRANSFER_SYNTAXES
    private = pynetdicom_globals.ALL_TRANSFER_SYNTAXES
    monkeypatch.delattr(pynetdicom, "ALL_TRANSFER_SYNTAXES")
    monkeypatch.setattr(pynetdicom_globals, "ALL_TRANSFER_SYNTAXES", private)
    try:
        assert load_all_transfer_syntaxes() is private
    finally:
        pynetdicom.ALL_TRANSFER_SYNTAXES = public


def test_configure_receive_runtime_changes_only_explicit_flags() -> None:
    config = SimpleNamespace(
        LOG_HANDLER_LEVEL="original",
        UNRESTRICTED_STORAGE_SERVICE=False,
        STORE_RECV_CHUNKED_DATASET=False,
        unrelated="preserved",
    )

    configure_receive_runtime(config)

    assert config.LOG_HANDLER_LEVEL == "none"
    assert config.UNRESTRICTED_STORAGE_SERVICE is True
    assert config.STORE_RECV_CHUNKED_DATASET is True
    assert config.unrelated == "preserved"


def test_add_supported_contexts_accepts_strings_and_context_objects() -> None:
    class FakeAE:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Any]] = []

        def add_supported_context(self, abstract_syntax: str, transfer_syntaxes: Any) -> None:
            self.calls.append((abstract_syntax, transfer_syntaxes))

    transfer_syntaxes = object()
    ae = FakeAE()
    add_supported_contexts(
        ae,
        ["1.2.3", SimpleNamespace(abstract_syntax="1.2.4")],
        transfer_syntaxes,
    )

    assert ae.calls == [("1.2.3", transfer_syntaxes), ("1.2.4", transfer_syntaxes)]
