"""Generate the published Phase 09 live-stream contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumora_probe.shared.events import EventEnvelope

OUTPUT = Path("docs/generated/asyncapi-v1.json")


def build_document() -> dict[str, Any]:
    """Build a deterministic equivalent AsyncAPI document."""

    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Lumora Probe live streams",
            "version": "1.0.0",
            "description": "WebSocket contracts for canonical events and mounted UI fragments.",
        },
        "servers": {
            "local": {
                "host": "localhost",
                "pathname": "/",
                "protocol": "ws",
                "description": "Loopback development endpoint; deployment TLS is external.",
            }
        },
        "channels": {
            "eventStream": {
                "address": "/api/v1/events/stream",
                "description": "Canonical JSON event batches for consumers.",
                "messages": {
                    "ready": {"$ref": "#/components/messages/Ready"},
                    "events": {"$ref": "#/components/messages/EventBatch"},
                    "protocolError": {"$ref": "#/components/messages/ProtocolError"},
                },
            },
            "uiStream": {
                "address": "/ws/ui",
                "description": "Server-rendered HTMX fragments for mounted views.",
                "messages": {
                    "ready": {"$ref": "#/components/messages/Ready"},
                    "fragments": {"$ref": "#/components/messages/FragmentBatch"},
                    "protocolError": {"$ref": "#/components/messages/ProtocolError"},
                },
            },
        },
        "operations": {
            "consumeEvents": {
                "action": "receive",
                "channel": {"$ref": "#/channels/eventStream"},
            },
            "consumeFragments": {
                "action": "receive",
                "channel": {"$ref": "#/channels/uiStream"},
            },
        },
        "components": {
            "messages": {
                "Ready": {
                    "payload": {
                        "type": "object",
                        "required": ["type", "version", "client_id", "resume"],
                        "properties": {
                            "type": {"const": "ready"},
                            "version": {"type": "integer", "const": 1},
                            "client_id": {"type": "string"},
                            "resume": {"type": "boolean"},
                        },
                    }
                },
                "EventBatch": {
                    "payload": {
                        "type": "object",
                        "required": ["type", "version", "events", "dropped_count"],
                        "properties": {
                            "type": {"const": "events"},
                            "version": {"type": "integer", "const": 1},
                            "replayed": {"type": "boolean"},
                            "events": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/EventEnvelope"},
                            },
                            "dropped_count": {"type": "integer", "minimum": 0},
                            "dropped_sequences": {"type": "array", "items": {"type": "integer"}},
                        },
                    }
                },
                "FragmentBatch": {
                    "payload": {
                        "type": "object",
                        "required": ["type", "version", "page", "fragments", "dropped_count"],
                        "properties": {
                            "type": {"const": "fragments"},
                            "version": {"type": "integer", "const": 1},
                            "page": {"type": "string"},
                            "fragments": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Fragment"},
                            },
                            "dropped_count": {"type": "integer", "minimum": 0},
                            "dropped_sequences": {"type": "array", "items": {"type": "integer"}},
                        },
                    }
                },
                "ProtocolError": {
                    "payload": {
                        "type": "object",
                        "required": ["type", "version", "code", "message"],
                        "properties": {
                            "type": {"const": "error"},
                            "version": {"type": "integer", "const": 1},
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "remediation": {"type": "string"},
                        },
                    }
                },
            },
            "schemas": {
                "EventEnvelope": EventEnvelope.model_json_schema(),
                "Fragment": {
                    "type": "object",
                    "required": ["panel", "target", "html"],
                    "properties": {
                        "panel": {"type": "string"},
                        "target": {"type": "string"},
                        "html": {"type": "string"},
                    },
                },
            },
        },
    }


def render() -> str:
    """Return the canonical artifact bytes as text."""

    return json.dumps(build_document(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
