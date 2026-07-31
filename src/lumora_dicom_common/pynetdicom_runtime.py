"""Narrow, product-neutral pynetdicom runtime compatibility helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def load_all_transfer_syntaxes() -> Any:
    """Load pynetdicom's all-transfer-syntax collection across supported layouts."""
    try:
        from pynetdicom import ALL_TRANSFER_SYNTAXES
    except ImportError:
        from pynetdicom._globals import ALL_TRANSFER_SYNTAXES
    return ALL_TRANSFER_SYNTAXES


def configure_receive_runtime(config: Any) -> None:
    """Apply the three explicit receive settings shared by both SCP callers."""
    config.LOG_HANDLER_LEVEL = "none"
    config.UNRESTRICTED_STORAGE_SERVICE = True
    config.STORE_RECV_CHUNKED_DATASET = True


def add_supported_contexts(ae: Any, contexts: Iterable[Any], transfer_syntaxes: Any) -> None:
    """Wire caller-selected presentation contexts onto an existing AE."""
    for context in contexts:
        abstract_syntax = getattr(context, "abstract_syntax", context)
        ae.add_supported_context(str(abstract_syntax), transfer_syntaxes)


__all__ = [
    "add_supported_contexts",
    "configure_receive_runtime",
    "load_all_transfer_syntaxes",
]
