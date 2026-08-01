# Capture Engine

Lumora Probe keeps two evidence lifecycles:

- **Ring buffer:** always-on, bounded, enabled by default. Default retention is 30 minutes
  and 2 GiB. Records are persisted under `LUMORA_DATA_DIR/ringbuffer/segments/` with atomic
  `metadata.json` when the engine is composed with `DataPaths.ringbuffer`. Legacy
  `records.jsonl` data migrates on first successful start.
- **Capture session:** explicit, unbounded until completed or interrupted. A session is
  sealed as a self-contained capture directory under the configured captures root.

## Privacy mode

Sites that cannot retain DICOM objects by default can set:

```text
LUMORA_RING_BUFFER_EVENTS_ONLY=true
```

The runtime setting `ring_buffer_events_only` has the same effect when configured through
`settings.toml`. Events remain available for timeline and troubleshooting work; protocol
records and object bytes are not retained by the ring buffer.

## Promotion

A retained time window can be promoted with `CaptureEngine.promote_window()`. Promotion:

1. Selects records still inside the requested window.
2. Copies event and PDU records without reparsing them.
3. Copies object bytes through the content-addressed object store.
4. Seals a new capture manifest with requested and actual bounds, source aggregates, fidelity,
   clock anchor, and partial-aggregate information.

A window beginning after `AssociationStarted` or ending before `AssociationReleased` /
`AssociationAborted` is marked `partial`. Protocol replay must refuse such a capture when
negotiation evidence is missing; promotion never invents the missing records.

## Shutdown and recovery

Lifecycle shutdown stops new work, drains the capture queue, flushes writers, and seals active
sessions as interrupted if the service is stopped. If the shutdown deadline expires, the
lifecycle manager calls the capture service's interruption hook before reporting failure.

On rebuild, a trailing incomplete JSONL record is discarded, the manifest is marked
`interrupted`, and `index.db` is re-derived from the capture directory. Non-trailing invalid
records are refused rather than repaired.

## Fidelity

Supported capture streams are derived from what is present:

- `events` — canonical event envelopes only;
- `protocol` — events plus compact PDU trace;
- `objects` — object bytes without PDU trace;
- `wire` — refused until raw wire capture has its own approved implementation.

Events are persisted with `EventEnvelope.to_json_bytes()`, preserving the published envelope
serialization boundary. PDU records remain off the event bus.
