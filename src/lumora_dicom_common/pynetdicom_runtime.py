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


def patch_transport_socket_cleanup() -> None:
    """Work around pynetdicom 3.0.x leaving sockets open on shutdown errors.

    ``AssociationSocket._shutdown_socket`` closes only when ``shutdown`` succeeds.
    Python 3.13 commonly reports an already-disconnected peer as an ``OSError``;
    closing in ``finally`` keeps transport teardown warning-clean without changing
    association state handling.
    """
    try:
        import socket

        from pynetdicom.transport import AssociationSocket
    except ImportError:
        return

    if getattr(AssociationSocket, "_lumora_safe_socket_cleanup", False):
        return

    def safe_shutdown(association_socket: Any) -> None:
        raw_socket = getattr(association_socket, "socket", None)
        if raw_socket is None:
            return
        try:
            raw_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            try:
                raw_socket.close()
            except OSError:
                pass

    AssociationSocket._shutdown_socket = safe_shutdown
    AssociationSocket._lumora_safe_socket_cleanup = True


def configure_receive_runtime(config: Any) -> None:
    """Apply the three explicit receive settings shared by both SCP callers."""
    patch_transport_socket_cleanup()
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
    "patch_transport_socket_cleanup",
]
