# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Data-root layout, containment checks, and filesystem safety guards."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from .config import StartupConfig, is_uuid7
from .errors import NetworkFilesystemError, PathSecurityError, VersionMismatchError

DATA_DIRECTORY_VERSION = 1
_NETWORK_FILESYSTEM_TYPES = frozenset(
    {"nfs", "nfs4", "cifs", "smb", "smbfs", "afp", "sshfs", "fuse.sshfs", "davfs"}
)


@dataclass(frozen=True, slots=True)
class DataPaths:
    root: Path
    captures: Path
    ringbuffer: Path
    reports: Path
    logs: Path
    plugins: Path
    settings_file: Path
    index_db: Path
    app_db: Path
    version_file: Path
    additional_capture_roots: tuple[Path, ...] = ()

    @classmethod
    def from_config(cls, config: StartupConfig) -> DataPaths:
        root = config.data_dir.expanduser().resolve()
        captures = config.effective_captures_root()
        return cls(
            root=root,
            captures=captures,
            ringbuffer=root / "ringbuffer",
            reports=root / "reports",
            logs=root / "logs",
            plugins=root / "plugins",
            settings_file=root / "settings.toml",
            index_db=root / "index.db",
            app_db=root / "app.db",
            version_file=root / "version",
            additional_capture_roots=tuple(
                path.expanduser().resolve() for path in config.additional_capture_roots
            ),
        )

    def create_directories(self) -> None:
        for path in (
            self.root,
            self.captures,
            self.ringbuffer,
            self.reports,
            self.logs,
            self.plugins,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def initialise(self, *, network_detector: Callable[[Path], bool] | None = None) -> None:
        self.create_directories()
        ensure_version_marker(self.version_file)
        assert_local_filesystem(
            (self.index_db, self.app_db), detector=network_detector or is_network_filesystem
        )

    def allowed_capture_roots(self) -> tuple[Path, ...]:
        return (self.captures, *self.additional_capture_roots)


def _mount_filesystem_type(path: Path) -> str | None:
    if sys.platform.startswith("linux"):
        mounts = Path("/proc/mounts")
        if not mounts.is_file():
            return None
        resolved = path.expanduser().resolve()
        best_mount: tuple[int, str] | None = None
        for line in mounts.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) < 3:
                continue
            mount_point = Path(fields[1].replace("\\040", " "))
            try:
                resolved.relative_to(mount_point)
            except ValueError:
                continue
            candidate = (len(str(mount_point)), fields[2].lower())
            if best_mount is None or candidate[0] > best_mount[0]:
                best_mount = candidate
        return best_mount[1] if best_mount else None
    if sys.platform == "darwin":
        import subprocess

        result = subprocess.run(
            ["stat", "-f", "%T", str(path)], capture_output=True, text=True, check=False
        )
        return result.stdout.strip().lower() or None
    return None


def is_network_filesystem(path: Path) -> bool:
    if os.name == "nt" and str(path).startswith(("\\", "//")):
        return True
    filesystem_type = _mount_filesystem_type(path)
    if filesystem_type is None:
        return False
    return filesystem_type in _NETWORK_FILESYSTEM_TYPES or any(
        marker in filesystem_type for marker in ("nfs", "smb", "cifs", "sshfs")
    )


def assert_local_filesystem(
    paths: Iterable[Path], *, detector: Callable[[Path], bool] = is_network_filesystem
) -> None:
    for path in paths:
        if detector(path.parent):
            raise NetworkFilesystemError(
                code="LUMORA-CORE-PATH-001",
                message=f"SQLite path is on a network filesystem: {path}",
                remediation="Move LUMORA_DATA_DIR to a local filesystem; captures may remain on a share.",
                context={"path": str(path), "parent": str(path.parent)},
            )


def ensure_version_marker(path: Path, *, version: int = DATA_DIRECTORY_VERSION) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = path.read_text(encoding="utf-8").strip()
        try:
            existing = int(raw)
        except ValueError as exc:
            raise VersionMismatchError(
                code="LUMORA-CORE-PATH-002",
                message=f"Invalid data-directory version marker: {path}",
                remediation="Back up the data directory and replace the marker with a supported version.",
                context={"path": str(path), "value": raw},
            ) from exc
        if existing > version:
            raise VersionMismatchError(
                code="LUMORA-CORE-PATH-003",
                message=f"Data directory version {existing} is newer than supported version {version}",
                remediation="Upgrade Lumora Probe before opening this data directory.",
                context={"path": str(path), "existing": existing, "supported": version},
            )
        if existing != version:
            path.write_text(f"{version}\n", encoding="utf-8")
        return
    path.write_text(f"{version}\n", encoding="utf-8")


def assert_contained(path: Path, allowed_root: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    resolved_root = allowed_root.expanduser().resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise PathSecurityError(
            code="LUMORA-CORE-PATH-004",
            message=f"Path escapes allowed root: {path}",
            remediation="Use a capture identifier and filename contained by the configured capture root.",
            context={"path": str(path), "allowed_root": str(allowed_root)},
        ) from exc
    return resolved_path


def resolve_capture_path(
    capture_id: str, *, allowed_root: Path, filename: str | None = None
) -> Path:
    if not is_uuid7(capture_id):
        raise PathSecurityError(
            code="LUMORA-CORE-PATH-005",
            message=f"Invalid capture_id: {capture_id!r}",
            remediation="Use the UUIDv7 capture identifier returned by the capture API.",
            context={"capture_id": capture_id},
        )
    capture_path = assert_contained(allowed_root / capture_id, allowed_root)
    if filename is None:
        return capture_path
    return assert_contained(capture_path / filename, allowed_root)
