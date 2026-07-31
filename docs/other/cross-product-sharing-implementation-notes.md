# Cross-Product Sharing Implementation Notes

**Date:** July 31, 2026
**Related ADR:** [ADR-0034](../adr/ADR-0034-neutral-dicom-common-infrastructure.md)

## Phase 2: `pynetdicom` extraction proof

### Call-site inventory

- `src/probe_lite/receiver.py::_build_ae` imports `AE`, storage contexts, `evt`,
  `Verification`, `ALL_TRANSFER_SYNTAXES` with a public/private fallback, and `_config`
  with a public/private fallback. It applies three receive-runtime flags, wires the Lite
  storage plus verification profile, and owns handlers, AE policy, and lifecycle.
- `src/lumora_probe/associations/network.py::DICOMListener._build_ae` imports `AE`, the
  public `ALL_TRANSFER_SYNTAXES`, storage/query-retrieve/verification profiles, and
  `_config`. It applies the same three receive-runtime flags, wires the application
  profile, and owns AE policy and lifecycle.
- `src/sender_lite/sender.py::{Sender.echo,Sender.send_study}` constructs synchronous SCUs,
  sets product-specific timeout policy, requests verification or catalog-derived contexts,
  associates once per Study Batch, classifies statuses, and owns result/exit behavior.
- `src/lumora_probe/associations/network.py::DICOMSCUClient.*` constructs synchronous work
  inside an async off-loop facade, requests verification/query-retrieve/store contexts,
  emits application results, and owns injected clock/ID, replay, and event behavior.

### Proof result

The focused proof tests run against the locked installed `pynetdicom` **3.0.4** and pass:

- public `ALL_TRANSFER_SYNTAXES` and all three caller-owned presentation-context families
  are available;
- the three receive-runtime settings can be applied idempotently without owning unrelated
  global state;
- context wiring can accept caller-supplied profiles and transfer syntaxes without a
  listener, SCU, callback, event, storage, clock, ID, or lifecycle abstraction.

### Explicit decision: GO, narrowly scoped

Proceed to Phase 3 with only these mechanical helpers:

1. lazy `ALL_TRANSFER_SYNTAXES` compatibility loading, preserving the Probe Lite public /
   private fallback;
2. explicit receive-runtime flag application for the three settings above;
3. parameterized supported-context wiring over caller-supplied context families.

The helpers must remain dependency/lifecycle primitives. Product callers retain dependency
failure messages, context-family choices, handlers, AE policy, logging, timeout policy,
association ownership, and all result semantics.

### Explicit decision: NO-GO for SCU construction

Do not extract minimal SCU AE construction. Sender Lite and Lumora Probe differ in timeout,
requested-context, async/off-loop, replay, cancellation, status, result, and association
ownership semantics. The helper would either duplicate too little to justify a boundary or
start absorbing product workflow policy.

### Stop condition

If Phase 3 needs a product callback, event, clock, ID generator, storage abstraction,
logging/configuration policy, async owner, lifecycle object, or global AE singleton, reject
the affected helper and retain the code in its product package.

## Phase 3: narrow `pynetdicom` adapter

Implemented `lumora_dicom_common.pynetdicom_runtime` with three mechanical helpers:

- `load_all_transfer_syntaxes()` preserves the public/private symbol fallback;
- `configure_receive_runtime()` applies only the three approved receive flags;
- `add_supported_contexts()` wires caller-supplied context profiles and transfer syntaxes.

Probe Lite and Lumora Probe listener setup now use these helpers. Listener handlers, AE
policy, context-family selection, lifecycle, logging, storage, event/audit behavior, and
application clock/ID ownership remain product-local. Sender Lite and application SCU
construction were intentionally not migrated under the Phase 2 NO-GO decision.
