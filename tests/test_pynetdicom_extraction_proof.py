"""Test-only proof for the proposed narrow pynetdicom adapter surface."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pynetdicom
from pynetdicom import (
    ALL_TRANSFER_SYNTAXES,
    AllStoragePresentationContexts,
    QueryRetrievePresentationContexts,
    VerificationPresentationContexts,
)


def _apply_receive_runtime_flags(config: Any) -> None:
    """Model the only global settings a neutral runtime helper may own."""
    config.LOG_HANDLER_LEVEL = "none"
    config.UNRESTRICTED_STORAGE_SERVICE = True
    config.STORE_RECV_CHUNKED_DATASET = True


def _add_supported_contexts(ae: Any, contexts: list[Any], transfer_syntaxes: Any) -> None:
    """Model parameterized presentation-context wiring without lifecycle state."""
    for context in contexts:
        ae.add_supported_context(str(context.abstract_syntax), transfer_syntaxes)


def test_installed_pynetdicom_surface_supports_both_receive_profiles() -> None:
    assert pynetdicom.__version__ == "3.0.4"
    assert ALL_TRANSFER_SYNTAXES
    assert AllStoragePresentationContexts
    assert QueryRetrievePresentationContexts
    assert VerificationPresentationContexts


def test_receive_runtime_proof_changes_only_explicit_global_flags() -> None:
    config = SimpleNamespace(
        LOG_HANDLER_LEVEL="original",
        UNRESTRICTED_STORAGE_SERVICE=False,
        STORE_RECV_CHUNKED_DATASET=False,
        unrelated="preserved",
    )

    _apply_receive_runtime_flags(config)

    assert config.LOG_HANDLER_LEVEL == "none"
    assert config.UNRESTRICTED_STORAGE_SERVICE is True
    assert config.STORE_RECV_CHUNKED_DATASET is True
    assert config.unrelated == "preserved"


def test_context_proof_accepts_caller_supplied_profiles_and_transfer_syntaxes() -> None:
    class FakeAE:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Any]] = []

        def add_supported_context(self, abstract_syntax: str, transfer_syntaxes: Any) -> None:
            self.calls.append((abstract_syntax, transfer_syntaxes))

    ae = FakeAE()
    contexts = [
        *AllStoragePresentationContexts[:1],
        *QueryRetrievePresentationContexts[:1],
        *VerificationPresentationContexts[:1],
    ]

    _add_supported_contexts(ae, contexts, ALL_TRANSFER_SYNTAXES)

    assert len(ae.calls) == 3
    assert all(transfer_syntaxes is ALL_TRANSFER_SYNTAXES for _, transfer_syntaxes in ae.calls)
