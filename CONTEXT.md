# Probe Lite Tools

Vocabulary shared by the lightweight DICOM receiver and its planned sender counterpart.

## Language

**Catalog**:
An in-memory inventory of valid DICOM instances discovered beneath one input directory, grouped by Study and Series.
_Avoid_: Database, index, manifest

**Study Batch**:
All cataloged Series and Instances belonging to one Study and treated as one sending unit.
_Avoid_: Transfer, job, package

**Sender Run**:
A one-shot operation that catalogs an input directory, sends each Study Batch in turn, then exits.
_Avoid_: Session, service, daemon

**Study Association**:
The single DICOM association opened for one Study Batch and released after every sendable Instance has received a C-STORE outcome.
_Avoid_: Single transfer, connection

**Sendable Instance**:
A discovered DICOM file with the identifiers and transfer-syntax metadata required for C-STORE transmission.
_Avoid_: Valid file, image

**Catalog Conflict**:
Two or more discovered files that claim the same SOP Instance UID, making every copy in that set ineligible for sending.
_Avoid_: Duplicate file

**Sender Lite**:
The one-shot DICOM sender that catalogs an input directory and submits Study Batches to a remote receiver.
_Avoid_: Probe sender, client, uploader

**Echo Run**:
An explicitly requested connectivity check that performs one C-ECHO operation and exits without cataloging or sending Instances.
_Avoid_: Preflight, health check
