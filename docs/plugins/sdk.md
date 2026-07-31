# Lumora Probe Plugin SDK

**SDK version:** `1.0` (major `1`)

Lumora Probe plugins are trusted in-process Python code. The SDK provides stable hook
specifications and contracts DTOs; it does **not** sandbox, restrict capabilities, or
interrupt a running hook. An enabled plugin can do anything the Lumora process can.
Manifest capabilities are disclosure for operator consent only.

## Public surface

Plugins import only from `lumora_probe.plugins.api` and
`lumora_probe.plugins.contracts`:

- `on_event(event)` observes immutable event DTOs.
- `analyze(context)` returns `FindingDTO` values.
- `contribute_report(context)` returns report contribution DTOs.
- `register_commands()` returns command metadata.
- `register_settings()` returns setting metadata.

Plugins never receive Lumora aggregates or repositories. Findings cite observed event
sequences and cannot mutate persisted events.

## Manifest

Each plugin directory contains `manifest.json` and its entry-point module:

```json
{
  "id": "vendor.example",
  "name": "Example Plugin",
  "version": "1.0.0",
  "author": "Vendor",
  "description": "Example public-SDK plugin",
  "capabilities": ["analysis"],
  "sdk": {"min_major": 1, "max_major": 1},
  "entry_point": "plugin:plugin",
  "hooks": ["analyze"]
}
```

The loader validates the manifest, SDK range, entry point, and every declared hook before
activation. Incompatible SDK majors are refused at load.

## Lifecycle and containment

Plugins are discovered under `LUMORA_DATA_DIR/plugins/` and are disabled by default. The
CLI places a plugin on disk; the API and UI only list, inspect, enable, and disable. Enabling
or disabling is persisted for the next restart because enabling imports and executes code.
There is no API installation route.

Exceptions are converted to an `ErrorRaised` diagnostic carrying plugin ID and hook. Repeated
failures disable the plugin. A hook exceeding its injected monotonic budget produces a
`WarningRaised` diagnostic and is disabled after repeated breaches. The budget measures and
disables; it cannot interrupt an infinite loop in the same Python process.

## Versioning and deprecation

- Major SDK changes increment `PLUGIN_SDK_MAJOR`; incompatible majors refuse to load.
- Additive DTO fields and hooks are introduced in a compatible minor release.
- A deprecated public symbol remains documented and supported for **two minor releases**.
  The release containing the replacement starts the window; removal occurs only after the
  second subsequent minor release.
- A breaking removal requires a new SDK major and migration notes.

## Commands

```console
lumora plugins install ./vendor.example --data-dir "$LUMORA_DATA_DIR"
```

The command validates and copies the directory. Review source and manifest before enabling,
then restart Lumora Probe. Installation never occurs through the unauthenticated API.

## Example

See `examples/plugins/example_plugin/`. It uses only the public SDK imports and can be
loaded from a plugin directory after deliberate filesystem placement.
