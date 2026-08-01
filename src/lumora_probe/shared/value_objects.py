"""Framework-free immutable value objects used by domain aggregates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from lumora_dicom_common.identifiers import inspect_ae_title, inspect_uid

from .errors import domain_invariant


def _as_uid(value: DICOMUID | str, *, field: str = "uid") -> DICOMUID:
    if isinstance(value, DICOMUID):
        return value
    return DICOMUID(value)


@dataclass(frozen=True, slots=True)
class AETitle:
    """A DICOM application entity title: one to sixteen ASCII bytes."""

    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise domain_invariant("AE title must be a string", field="value", value=self.value)
        if not self.value.strip() or any(ord(character) < 0x20 for character in self.value):
            raise domain_invariant(
                "AE title must contain printable, non-whitespace characters",
                field="value",
                value=self.value,
            )
        inspection = inspect_ae_title(self.value)
        if inspection.reason == "non_ascii":
            raise domain_invariant("AE title must contain only ASCII characters", field="value")
        if inspection.reason == "invalid_length":
            raise domain_invariant(
                "AE title must be 1 to 16 ASCII bytes", field="value", value=self.value
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DICOMUID:
    """A valid DICOM UI value represented as a dotted decimal UID."""

    value: str

    def __post_init__(self) -> None:
        inspection = inspect_uid(self.value) if type(self.value) is str else None
        if inspection is None or inspection.reason is not None:
            raise domain_invariant(
                "UID must be dotted decimal digits and at most 64 characters",
                field="value",
                value=self.value,
            )

    def __str__(self) -> str:
        return self.value


# Common spellings used by DICOM and application code.
DicomUID = DICOMUID
UID = DICOMUID
SOPClassUID = DICOMUID
TransferSyntaxUID = DICOMUID


@dataclass(frozen=True, slots=True)
class NetworkEndpoint:
    """A host and TCP port used by an association leg."""

    host: str
    port: int

    def __post_init__(self) -> None:
        if type(self.host) is not str or not self.host.strip():
            raise domain_invariant("endpoint host must be non-empty", field="host", value=self.host)
        if any(character.isspace() for character in self.host):
            raise domain_invariant("endpoint host must not contain whitespace", field="host")
        if type(self.port) is not int or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise domain_invariant(
                "endpoint port must be between 1 and 65535", field="port", value=self.port
            )

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class TransferSyntax:
    """A DICOM transfer syntax identified by its UID."""

    uid: DICOMUID | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", _as_uid(self.uid, field="uid"))

    @property
    def value(self) -> str:
        return self.uid.value if isinstance(self.uid, DICOMUID) else self.uid

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PresentationContext:
    """An odd presentation-context ID, abstract syntax, and transfer syntaxes."""

    context_id: int
    abstract_syntax: DICOMUID | str
    transfer_syntaxes: tuple[TransferSyntax | DICOMUID | str, ...]

    def __post_init__(self) -> None:
        if (
            type(self.context_id) is not int
            or isinstance(self.context_id, bool)
            or not 1 <= self.context_id <= 255
            or self.context_id % 2 == 0
        ):
            raise domain_invariant(
                "presentation-context ID must be an odd integer from 1 to 255",
                field="context_id",
                value=self.context_id,
            )
        object.__setattr__(
            self, "abstract_syntax", _as_uid(self.abstract_syntax, field="abstract_syntax")
        )
        if isinstance(self.transfer_syntaxes, (str, bytes)):
            raise domain_invariant(
                "presentation context must contain one or more transfer syntaxes",
                field="transfer_syntaxes",
            )
        transfer_syntaxes = tuple(
            transfer_syntax
            if isinstance(transfer_syntax, TransferSyntax)
            else TransferSyntax(transfer_syntax)
            for transfer_syntax in self.transfer_syntaxes
        )
        if not transfer_syntaxes:
            raise domain_invariant(
                "presentation context must contain one or more transfer syntaxes",
                field="transfer_syntaxes",
            )
        object.__setattr__(self, "transfer_syntaxes", transfer_syntaxes)

    @property
    def id(self) -> int:
        return self.context_id


@dataclass(frozen=True, slots=True)
class Timestamp:
    """A timezone-aware wall-clock timestamp."""

    value: datetime

    def __post_init__(self) -> None:
        if type(self.value) is not datetime:
            raise domain_invariant("timestamp must be a datetime", field="value", value=self.value)
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise domain_invariant("timestamp must be timezone-aware", field="value")

    def __str__(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True, slots=True)
class Duration:
    """A non-negative elapsed duration."""

    value: timedelta

    def __post_init__(self) -> None:
        if type(self.value) is not timedelta:
            raise domain_invariant("duration must be a timedelta", field="value", value=self.value)
        if self.value < timedelta(0):
            raise domain_invariant("duration must be non-negative", field="value", value=self.value)


@dataclass(frozen=True, slots=True)
class FilePath:
    """A non-empty path value; containment belongs to the core boundary."""

    value: Path | str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Path):
            object.__setattr__(self, "value", Path(self.value))
        if not str(self.value):
            raise domain_invariant("file path must be non-empty", field="value")

    def __str__(self) -> str:
        return (
            self.value.as_posix() if isinstance(self.value, Path) else Path(self.value).as_posix()
        )


@dataclass(frozen=True, slots=True)
class DICOMTag:
    """A DICOM tag represented by its 16-bit group and element."""

    group: int
    element: int

    def __post_init__(self) -> None:
        for field_name, value in (("group", self.group), ("element", self.element)):
            if type(value) is not int or isinstance(value, bool) or not 0 <= value <= 0xFFFF:
                raise domain_invariant(
                    f"DICOM tag {field_name} must be a 16-bit integer",
                    field=field_name,
                    value=value,
                )

    def __str__(self) -> str:
        return f"({self.group:04X},{self.element:04X})"


@dataclass(frozen=True, slots=True)
class PixelDimensions:
    """Positive image row and column dimensions."""

    rows: int
    columns: int

    def __post_init__(self) -> None:
        for field_name, value in (("rows", self.rows), ("columns", self.columns)):
            if type(value) is not int or isinstance(value, bool) or value <= 0:
                raise domain_invariant(
                    f"pixel dimension {field_name} must be a positive integer",
                    field=field_name,
                    value=value,
                )


@dataclass(frozen=True, slots=True)
class WindowLevel:
    """DICOM display window center."""

    value: float

    def __post_init__(self) -> None:
        if type(self.value) not in (int, float) or not math.isfinite(self.value):
            raise domain_invariant("window level must be finite", field="value", value=self.value)


@dataclass(frozen=True, slots=True)
class WindowWidth:
    """DICOM display window width, which must be positive."""

    value: float

    def __post_init__(self) -> None:
        if type(self.value) not in (int, float) or not math.isfinite(self.value) or self.value <= 0:
            raise domain_invariant(
                "window width must be positive and finite", field="value", value=self.value
            )


__all__ = [
    "DICOMUID",
    "UID",
    "AETitle",
    "DICOMTag",
    "DicomUID",
    "Duration",
    "FilePath",
    "NetworkEndpoint",
    "PixelDimensions",
    "PresentationContext",
    "SOPClassUID",
    "Timestamp",
    "TransferSyntax",
    "TransferSyntaxUID",
    "WindowLevel",
    "WindowWidth",
]
