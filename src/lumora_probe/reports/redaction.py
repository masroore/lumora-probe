"""Configurable, honest tag-level redaction for pydicom datasets."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from pydicom.datadict import keyword_for_tag, tag_for_keyword
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.tag import BaseTag, Tag
from pydicom.uid import (
    EnhancedUSVolumeStorage,
    MultiFrameGrayscaleByteSecondaryCaptureImageStorage,
    MultiFrameGrayscaleWordSecondaryCaptureImageStorage,
    MultiFrameSingleBitSecondaryCaptureImageStorage,
    MultiFrameTrueColorSecondaryCaptureImageStorage,
    SecondaryCaptureImageStorage,
    UltrasoundImageStorage,
    UltrasoundMultiFrameImageStorage,
)

type TagLike = int | str | BaseTag


class IdSource(Protocol):
    """Injected identity source used to create replacement DICOM UIDs."""

    def new_id(self) -> str: ...


def _coerce_tag(value: TagLike) -> Tag:  # pyright: ignore[reportGeneralTypeIssues, reportUnknownParameterType]
    if isinstance(value, str):
        keyword_tag = tag_for_keyword(value)
        if keyword_tag is not None:
            return Tag(keyword_tag)
        try:
            return Tag(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unknown DICOM tag: {value}") from exc
    return Tag(value)


# These are deliberately a profile, not a claim that this list covers every sensitive value.
_DEFAULT_REDACTED_TAGS = (
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientBirthTime",
    "OtherPatientIDs",
    "OtherPatientNames",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "ReferringPhysicianName",
    "ReferringPhysicianAddress",
    "ReferringPhysicianTelephoneNumbers",
    "InstitutionName",
    "InstitutionAddress",
    "StationName",
    "InstitutionalDepartmentName",
    "OperatorsName",
    "PhysiciansOfRecord",
    "PerformingPhysicianName",
    "NameOfPhysiciansReadingStudy",
    "AdmittingDiagnosesDescription",
    "AccessionNumber",
    "StudyDescription",
    "SeriesDescription",
    "ProtocolName",
    "ClinicalTrialSubjectID",
    "ClinicalTrialTimePointID",
    "AdditionalPatientHistory",
    "PatientComments",
    "ImageComments",
    "DerivationDescription",
    "RequestedProcedureDescription",
    "ScheduledProcedureStepDescription",
)

_TEXT_VRS = frozenset({"LO", "LT", "PN", "SH", "ST", "UC", "UR", "UT"})

# SOP Class UIDs remain usable identifiers. Instance and reference UIDs are remapped.
_STATIC_UID_KEYWORDS = frozenset(
    {
        "CodingSchemeUID",
        "ContextGroupExtensionCreatorUID",
        "ImplementationClassUID",
        "MediaStorageSOPClassUID",
        "OriginalSpecializedSOPClassUID",
        "RelatedGeneralSOPClassUID",
        "SOPClassUID",
        "TransferSyntaxUID",
    }
)

_SECONDARY_CAPTURE_CLASSES = frozenset(
    {
        str(SecondaryCaptureImageStorage),
        str(MultiFrameSingleBitSecondaryCaptureImageStorage),
        str(MultiFrameGrayscaleByteSecondaryCaptureImageStorage),
        str(MultiFrameGrayscaleWordSecondaryCaptureImageStorage),
        str(MultiFrameTrueColorSecondaryCaptureImageStorage),
    }
)
_ULTRASOUND_CLASSES = frozenset(
    {
        str(UltrasoundImageStorage),
        str(UltrasoundMultiFrameImageStorage),
        str(EnhancedUSVolumeStorage),
    }
)


@dataclass(frozen=True, slots=True)
class RedactionProfile:
    """Tag actions and private-tag knowledge used by one redaction operation."""

    remove_tags: Iterable[TagLike] = field(default_factory=lambda: _DEFAULT_REDACTED_TAGS)
    replace_tags: Mapping[TagLike, str] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    recognized_private_tags: Iterable[TagLike] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        remove_tags = frozenset(_coerce_tag(tag) for tag in self.remove_tags)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        replace_tags = {_coerce_tag(tag): value for tag, value in self.replace_tags.items()}  # pyright: ignore[reportUnknownVariableType]
        recognized_private_tags = frozenset(  # pyright: ignore[reportUnknownVariableType]
            _coerce_tag(tag)
            for tag in self.recognized_private_tags  # pyright: ignore[reportUnknownArgumentType]
        )
        overlap = remove_tags.intersection(replace_tags)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        if overlap:
            tags = ", ".join(str(tag) for tag in sorted(overlap))  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            raise ValueError(f"tag cannot be both removed and replaced: {tags}")
        if any(not isinstance(value, str) for value in replace_tags.values()):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("replacement values must be strings")

        object.__setattr__(self, "remove_tags", remove_tags)
        object.__setattr__(self, "replace_tags", MappingProxyType(replace_tags))  # pyright: ignore[reportUnknownArgumentType]
        object.__setattr__(self, "recognized_private_tags", recognized_private_tags)


DEFAULT_REDACTION_PROFILE = RedactionProfile()


@dataclass(frozen=True, slots=True)
class RedactionWarning:
    """A limitation or unverifiable-content warning emitted with redacted output."""

    code: str
    message: str
    tag: Tag | None = None  # pyright: ignore[reportGeneralTypeIssues]


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Redacted dataset plus warnings and the UID mapping used for this copy."""

    dataset: Dataset
    warnings: tuple[RedactionWarning, ...]
    redacted_tags: tuple[Tag, ...]  # pyright: ignore[reportGeneralTypeIssues]
    uid_mapping: Mapping[str, str]

    @property
    def output(self) -> Dataset:
        """Return the redacted dataset copy."""
        return self.dataset


class DatasetRedactor:
    """Apply one configurable redaction profile to a deep copy of a dataset."""

    def __init__(
        self,
        id_generator: IdSource,
        profile: RedactionProfile = DEFAULT_REDACTION_PROFILE,
    ) -> None:
        self._id_generator = id_generator
        self._profile = profile

    def redact(
        self, dataset: Dataset, *, uid_mapping: dict[str, str] | None = None
    ) -> RedactionResult:
        """Redact ``dataset`` without mutating its source object.

        A caller may provide a shared mapping when redacting several objects so repeated
        Study/Series/Instance references remain consistent across the output capture.
        """
        output = deepcopy(dataset)
        warnings: list[RedactionWarning] = []
        warning_keys: set[tuple[str, int | None, str]] = set()
        redacted_tags: set[Tag] = set()  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]
        active_uid_mapping = uid_mapping if uid_mapping is not None else {}

        self._visit_dataset(  # pyright: ignore[reportUnknownMemberType]
            output,
            warnings=warnings,
            warning_keys=warning_keys,
            redacted_tags=redacted_tags,
            uid_mapping=active_uid_mapping,
        )
        file_meta = getattr(output, "file_meta", None)
        if isinstance(file_meta, Dataset):
            self._visit_dataset(  # pyright: ignore[reportUnknownMemberType]
                file_meta,
                warnings=warnings,
                warning_keys=warning_keys,
                redacted_tags=redacted_tags,
                uid_mapping=active_uid_mapping,
            )

        return RedactionResult(
            dataset=output,
            warnings=tuple(warnings),
            redacted_tags=tuple(sorted(redacted_tags)),  # pyright: ignore[reportUnknownArgumentType]
            uid_mapping=MappingProxyType(dict(active_uid_mapping)),
        )

    def _visit_dataset(
        self,
        dataset: Dataset,
        *,
        warnings: list[RedactionWarning],
        warning_keys: set[tuple[str, int | None, str]],
        redacted_tags: set[Tag],  # pyright: ignore[reportGeneralTypeIssues, reportUnknownParameterType]
        uid_mapping: dict[str, str],
    ) -> None:
        self._warn_dataset(dataset, warnings, warning_keys)

        for element in tuple(dataset):
            tag = Tag(element.tag)
            self._warn_element(element, warnings, warning_keys)
            if tag in self._profile.remove_tags:
                del dataset[tag]
                redacted_tags.add(tag)  # pyright: ignore[reportUnknownMemberType]
                continue

            replacement = self._profile.replace_tags.get(tag)
            if replacement is not None:
                element.value = replacement
            elif element.VR == "UI" and self._is_remappable_uid(element):
                element.value = self._remap_uid_value(element.value, uid_mapping)

            if element.VR == "SQ":
                for item in element.value:  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]
                    if isinstance(item, Dataset):
                        self._visit_dataset(  # pyright: ignore[reportUnknownMemberType]
                            item,
                            warnings=warnings,
                            warning_keys=warning_keys,
                            redacted_tags=redacted_tags,
                            uid_mapping=uid_mapping,
                        )

    def _warn_dataset(
        self,
        dataset: Dataset,
        warnings: list[RedactionWarning],
        warning_keys: set[tuple[str, int | None, str]],
    ) -> None:
        burned_in = dataset.get("BurnedInAnnotation")
        if burned_in is not None:
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="burned_in_annotation",
                    message=(
                        f"BurnedInAnnotation={str(burned_in).strip()!r}; pixel content was not "
                        "inspected for embedded identifiers."
                    ),
                    tag=Tag(tag_for_keyword("BurnedInAnnotation")),  # pyright: ignore[reportArgumentType]
                ),
            )

        sop_class = str(dataset.get("SOPClassUID", ""))
        sop_tag = Tag(tag_for_keyword("SOPClassUID"))  # pyright: ignore[reportArgumentType]
        if sop_class in _SECONDARY_CAPTURE_CLASSES:
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="secondary_capture_sop_class",
                    message=(
                        "Secondary Capture SOP Class may contain identifiers in screenshot "
                        "pixels; pixel content was not inspected."
                    ),
                    tag=sop_tag,
                ),
            )
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="screenshot_sop_class",
                    message=(
                        "Screenshot-like pixel content may contain identifiers; pixel content "
                        "was not inspected."
                    ),
                    tag=sop_tag,
                ),
            )
        elif sop_class in _ULTRASOUND_CLASSES:
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="ultrasound_sop_class",
                    message=(
                        "Ultrasound SOP Class may contain identifiers in pixels; pixel content "
                        "was not inspected."
                    ),
                    tag=sop_tag,
                ),
            )
        elif str(dataset.get("Modality", "")).strip().upper() == "SC":
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="screenshot_sop_class",
                    message=(
                        "Screenshot modality may contain identifiers in pixels; pixel content "
                        "was not inspected."
                    ),
                    tag=sop_tag,
                ),
            )

    def _warn_element(
        self,
        element: DataElement,
        warnings: list[RedactionWarning],
        warning_keys: set[tuple[str, int | None, str]],
    ) -> None:
        tag = Tag(element.tag)
        if tag.is_private and tag not in self._profile.recognized_private_tags:
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="unrecognized_private_tag",
                    message=f"Unrecognized private tag {tag} was present and may carry identifiers.",
                    tag=tag,
                ),
            )

        if element.VR in _TEXT_VRS and _has_value(element.value):
            keyword = keyword_for_tag(tag) or str(tag)
            self._add_warning(
                warnings,
                warning_keys,
                RedactionWarning(
                    code="free_text_field",
                    message=f"Free-text field {keyword} was present and may carry identifiers.",
                    tag=tag,
                ),
            )

    @staticmethod
    def _add_warning(
        warnings: list[RedactionWarning],
        warning_keys: set[tuple[str, int | None, str]],
        warning: RedactionWarning,
    ) -> None:
        key = (warning.code, int(warning.tag) if warning.tag is not None else None, warning.message)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        if key not in warning_keys:
            warning_keys.add(key)
            warnings.append(warning)

    @staticmethod
    def _is_remappable_uid(element: DataElement) -> bool:
        keyword = keyword_for_tag(Tag(element.tag))
        if keyword in _STATIC_UID_KEYWORDS:
            return False
        return keyword.endswith("InstanceUID") or keyword in {
            "FrameOfReferenceUID",
            "SynchronizationFrameOfReferenceUID",
        }

    def _remap_uid_value(self, value: object, uid_mapping: dict[str, str]) -> object:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [self._remap_one_uid(str(item), uid_mapping) for item in value]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        return self._remap_one_uid(str(value), uid_mapping)

    def _remap_one_uid(self, source_uid: str, uid_mapping: dict[str, str]) -> str:
        if not source_uid:
            return source_uid
        mapped = uid_mapping.get(source_uid)
        if mapped is None:
            mapped = _uid_from_id(self._id_generator.new_id())
            uid_mapping[source_uid] = mapped
        return mapped


def redact_dataset(
    dataset: Dataset,
    id_generator: IdSource,
    profile: RedactionProfile = DEFAULT_REDACTION_PROFILE,
) -> RedactionResult:
    """Return a redacted copy of ``dataset`` using injected identities."""
    return DatasetRedactor(id_generator, profile).redact(dataset)


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_has_value(item) for item in value)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    return True


def _uid_from_id(identity: str) -> str:
    compact = identity.replace("-", "").strip()
    if not compact or any(character not in "0123456789abcdefABCDEF" for character in compact):
        raise ValueError("injected ID generator must return a UUID-shaped identity")
    value = int(compact, 16)
    uid = f"2.25.{value}"
    if len(uid) > 64:
        raise ValueError("generated UID exceeds the DICOM UID length limit")
    return uid


__all__ = [
    "DEFAULT_REDACTION_PROFILE",
    "DatasetRedactor",
    "RedactionProfile",
    "RedactionResult",
    "RedactionWarning",
    "redact_dataset",
]
