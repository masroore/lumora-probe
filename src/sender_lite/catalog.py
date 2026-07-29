"""Catalog model for Sender Lite.

Scans an input directory, validates DICOM files, detects duplicate SOP
Instance UIDs, and groups admissible instances into Studies/Series with
deterministic ordering.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydicom import dcmread
from pydicom.uid import UID

from lumora_lite_common import uids as _uids


class CatalogError(Exception):
    """A fatal catalog build failure (e.g. invalid input root)."""


# Reason codes for CatalogIssue
REASON_READ = "read_error"
REASON_MISSING_UID = "missing_uid"
REASON_INVALID_UID = "invalid_uid"
REASON_MULTI_VALUED_UID = "multi_valued_uid"
REASON_SOP_MISMATCH = "sop_class_mismatch"
REASON_SOP_INSTANCE_MISMATCH = "sop_instance_mismatch"
REASON_INVALID_TRANSFER_SYNTAX = "invalid_transfer_syntax"
REASON_FILE_META_MISSING = "file_meta_missing"
REASON_CONFLICT = "duplicate_sop_instance_uid"


@dataclass(frozen=True, slots=True)
class CatalogInstance:
    path: Path
    size_bytes: int
    study_uid: str
    series_uid: str
    sop_instance_uid: str
    sop_class_uid: str
    transfer_syntax_uid: str
    instance_number: int | None


@dataclass(frozen=True, slots=True)
class SeriesCatalog:
    series_uid: str
    instances: tuple[CatalogInstance, ...]


@dataclass(frozen=True, slots=True)
class StudyBatch:
    study_uid: str
    series: tuple[SeriesCatalog, ...]

    @property
    def instances(self) -> tuple[CatalogInstance, ...]:
        out: list[CatalogInstance] = []
        for s in self.series:
            out.extend(s.instances)
        return tuple(out)

    @property
    def presentation_requirements(self) -> tuple[tuple[str, str], ...]:
        seen: dict[tuple[str, str], None] = {}
        for inst in self.instances:
            key = (inst.sop_class_uid, inst.transfer_syntax_uid)
            if key not in seen:
                seen[key] = None
        return tuple(seen.keys())

    @property
    def total_bytes(self) -> int:
        return sum(inst.size_bytes for inst in self.instances)

    @property
    def instance_count(self) -> int:
        return len(self.instances)


@dataclass(frozen=True, slots=True)
class CatalogIssue:
    path: Path
    reason: str
    message: str
    sop_instance_uid: str | None = None


@dataclass(frozen=True, slots=True)
class Catalog:
    studies: tuple[StudyBatch, ...]
    issues: tuple[CatalogIssue, ...]
    scanned_count: int
    rejected_count: int
    sendable_count: int
    series_count: int
    study_count: int
    total_bytes: int


def _validate_uid(value: object) -> tuple[str | None, str | None]:
    """Return (uid_str, error_reason) for a UID-valued dataset attribute.

    Delegates shape/length/validity to :func:`lumora_lite_common.uids.validate_uid`
    and maps its generic reason categories onto Sender Lite's reason codes. A
    ``None`` reason means the UID is valid. See ADR-0028.
    """
    _reason_map = {
        _uids.REASON_MISSING: REASON_MISSING_UID,
        _uids.REASON_MULTI_VALUED: REASON_MULTI_VALUED_UID,
        _uids.REASON_INVALID: REASON_INVALID_UID,
    }
    uid, reason = _uids.validate_uid(value)
    if reason is None:
        return uid, None
    return None, _reason_map.get(reason, REASON_INVALID_UID)


def _parse_instance_number(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    # pydicom may wrap in IS (a str subclass) or ISfloat
    # Accept int-like decimal strings
    try:
        text = str(value).strip()
    except (TypeError, ValueError):
        return None
    if not text:
        return None
    # Must look like an integer (no decimal point, optional leading sign)
    stripped = text.lstrip("-+")
    if stripped.isdigit() and stripped:
        try:
            return int(text)
        except (TypeError, ValueError):
            return None
    # Try float -> int if it's a whole number (e.g., "1.0" or Decimal("1"))
    try:
        f = float(text)
        if f.is_integer():
            return int(f)
    except (TypeError, ValueError):
        pass
    return None


def _iter_candidates(input_root: Path) -> Iterator[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(input_root, followlinks=False):
        # Skip symlinked subdirectories
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            if os.path.islink(full):
                continue
            paths.append(Path(full))
    paths.sort()
    yield from paths


def _read_candidate(path: Path) -> tuple[CatalogInstance | None, CatalogIssue | None]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, CatalogIssue(path=path, reason=REASON_READ, message=str(exc))

    try:
        ds = dcmread(path, stop_before_pixels=True, force=False)
    except Exception as exc:  # noqa: BLE001  -- pydicom/malformed-file rejection per plan §8.2.6
        return None, CatalogIssue(path=path, reason=REASON_READ, message=str(exc))

    # Required dataset UIDs
    required_dataset = {
        "StudyInstanceUID": ds.get("StudyInstanceUID"),
        "SeriesInstanceUID": ds.get("SeriesInstanceUID"),
        "SOPInstanceUID": ds.get("SOPInstanceUID"),
        "SOPClassUID": ds.get("SOPClassUID"),
    }
    for name, val in required_dataset.items():
        if val is None:
            return None, CatalogIssue(
                path=path, reason=REASON_MISSING_UID, message=f"missing {name}"
            )

    study_uid, err = _validate_uid(ds.get("StudyInstanceUID"))
    if err or study_uid is None:
        return None, CatalogIssue(
            path=path, reason=err or REASON_MISSING_UID, message="invalid StudyInstanceUID"
        )
    series_uid, err = _validate_uid(ds.get("SeriesInstanceUID"))
    if err or series_uid is None:
        return None, CatalogIssue(
            path=path, reason=err or REASON_MISSING_UID, message="invalid SeriesInstanceUID"
        )
    sop_uid, err = _validate_uid(ds.get("SOPInstanceUID"))
    if err or sop_uid is None:
        return None, CatalogIssue(
            path=path, reason=err or REASON_MISSING_UID, message="invalid SOPInstanceUID"
        )
    sop_class, err = _validate_uid(ds.get("SOPClassUID"))
    if err or sop_class is None:
        return None, CatalogIssue(
            path=path, reason=err or REASON_MISSING_UID, message="invalid SOPClassUID"
        )

    # File meta
    file_meta = getattr(ds, "file_meta", None)
    if file_meta is None:
        return None, CatalogIssue(
            path=path, reason=REASON_FILE_META_MISSING, message="missing file meta"
        )

    fm_sop_instance, err = _validate_uid(file_meta.get("MediaStorageSOPInstanceUID"))
    if err:
        return None, CatalogIssue(
            path=path, reason=err, message="invalid MediaStorageSOPInstanceUID"
        )
    fm_sop_class, err = _validate_uid(file_meta.get("MediaStorageSOPClassUID"))
    if err:
        return None, CatalogIssue(path=path, reason=err, message="invalid MediaStorageSOPClassUID")
    fm_ts_raw = file_meta.get("TransferSyntaxUID")
    if fm_ts_raw is None:
        return None, CatalogIssue(
            path=path, reason=REASON_MISSING_UID, message="missing TransferSyntaxUID"
        )
    ts_uid, err = _validate_uid(fm_ts_raw)
    if err or ts_uid is None:
        return None, CatalogIssue(
            path=path, reason=err or REASON_MISSING_UID, message="invalid TransferSyntaxUID"
        )
    try:
        ts_obj = UID(ts_uid)
    except (TypeError, ValueError):
        return None, CatalogIssue(
            path=path, reason=REASON_INVALID_TRANSFER_SYNTAX, message="invalid TransferSyntaxUID"
        )
    if not ts_obj.is_transfer_syntax:
        return None, CatalogIssue(
            path=path,
            reason=REASON_INVALID_TRANSFER_SYNTAX,
            message=f"TransferSyntaxUID {ts_uid} is not a transfer syntax",
        )

    # Consistency
    if sop_class != fm_sop_class:
        return None, CatalogIssue(
            path=path,
            reason=REASON_SOP_MISMATCH,
            message="SOPClassUID != MediaStorageSOPClassUID",
        )
    if sop_uid != fm_sop_instance:
        return None, CatalogIssue(
            path=path,
            reason=REASON_SOP_INSTANCE_MISMATCH,
            message="SOPInstanceUID != MediaStorageSOPInstanceUID",
        )

    # InstanceNumber: accept int or int-like decimal string, else None
    try:
        inst_num_value = ds.get("InstanceNumber")
    except (ValueError, AttributeError):
        inst_num_value = None
    instance_number = _parse_instance_number(inst_num_value)

    return CatalogInstance(
        path=path,
        size_bytes=size,
        study_uid=study_uid,
        series_uid=series_uid,
        sop_instance_uid=sop_uid,
        sop_class_uid=sop_class,
        transfer_syntax_uid=ts_uid,
        instance_number=instance_number,
    ), None


def _sort_instances(instances: tuple[CatalogInstance, ...]) -> tuple[CatalogInstance, ...]:
    def key(inst: CatalogInstance) -> tuple[int, int | float, str]:
        if inst.instance_number is None:
            # After numbered; tiebreak by SOP UID
            return (1, 0, inst.sop_instance_uid)
        return (0, inst.instance_number, inst.sop_instance_uid)

    return tuple(sorted(instances, key=key))


def build_catalog(input_root: Path) -> Catalog:
    root = Path(input_root)
    if not root.exists():
        raise CatalogError(f"input root does not exist: {root}")
    if not root.is_dir():
        raise CatalogError(f"input root is not a directory: {root}")
    if root.is_symlink():
        raise CatalogError(f"input root is a symlink: {root}")

    issues: list[CatalogIssue] = []
    admissible: list[CatalogInstance] = []
    scanned = 0

    for path in _iter_candidates(root):
        scanned += 1
        inst, issue = _read_candidate(path)
        if issue is not None:
            issues.append(issue)
            continue
        assert inst is not None
        admissible.append(inst)

    # Duplicate SOP Instance UID detection
    groups: dict[str, list[CatalogInstance]] = {}
    for inst in admissible:
        groups.setdefault(inst.sop_instance_uid, []).append(inst)

    rejected = len(issues)
    final: list[CatalogInstance] = []
    for sop_uid, members in groups.items():
        if len(members) > 1:
            for m in members:
                issues.append(
                    CatalogIssue(
                        path=m.path,
                        reason=REASON_CONFLICT,
                        message=f"duplicate SOP Instance UID {sop_uid}",
                        sop_instance_uid=sop_uid,
                    )
                )
                rejected += 1
        else:
            final.append(members[0])

    # Group by Study -> Series
    studies_map: dict[str, dict[str, list[CatalogInstance]]] = {}
    for inst in final:
        studies_map.setdefault(inst.study_uid, {}).setdefault(inst.series_uid, []).append(inst)

    study_batches: list[StudyBatch] = []
    series_count = 0
    total_bytes = 0
    for study_uid in sorted(studies_map.keys()):
        series_map = studies_map[study_uid]
        series_list: list[SeriesCatalog] = []
        for series_uid in sorted(series_map.keys()):
            sorted_insts = _sort_instances(tuple(series_map[series_uid]))
            series_list.append(SeriesCatalog(series_uid=series_uid, instances=sorted_insts))
            series_count += 1
            total_bytes += sum(i.size_bytes for i in sorted_insts)
        study_batches.append(StudyBatch(study_uid=study_uid, series=tuple(series_list)))

    sendable = sum(sb.instance_count for sb in study_batches)

    return Catalog(
        studies=tuple(study_batches),
        issues=tuple(issues),
        scanned_count=scanned,
        rejected_count=rejected,
        sendable_count=sendable,
        series_count=series_count,
        study_count=len(study_batches),
        total_bytes=total_bytes,
    )
