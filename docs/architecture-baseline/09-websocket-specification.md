# 09-websocket-specification.md

> **Project:** Lumora Probe
>
> **Document:** WebSocket Specification
>
> **Status:** Architecture Baseline
>
> **Audience:** Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the high-level WebSocket architecture for Lumora Probe.

It establishes how clients receive live events, subscribe to streams, and monitor long-running operations. Implementation details are intentionally left to subsequent design documents.

---

# 2. Objectives

The WebSocket layer SHALL:

- Deliver real-time updates
- Stream domain events
- Support multiple concurrent clients
- Integrate with the event bus
- Scale independently of the REST API
- Remain backward compatible

---

# 3. Design Principles

- Event-driven
- Connection-oriented
- Stateless authentication
- Topic-based subscriptions
- Structured messages
- Graceful degradation

---

# 4. Connection Lifecycle

Typical lifecycle:

```
Connect
 ↓
Authenticate
 ↓
Subscribe
 ↓
Receive Events
 ↓
Unsubscribe
 ↓
Disconnect
```

Clients should reconnect automatically after transient failures.

---

# 5. Authentication

Implementations should support:

- Session authentication
- API Keys
- OAuth2/OIDC (future)
- Service accounts

Authentication should occur immediately after connection establishment.

---

# 6. Subscription Model

Typical subscriptions include:

- System events
- Association events
- Capture events
- Replay events
- Analysis events
- Report events
- Plugin events
- Log events

Subscriptions should be dynamic.

---

# 7. Channel Naming

Suggested channel hierarchy:

- system
- associations
- captures
- replays
- studies
- analysis
- reports
- plugins
- logs
- notifications

---

# 8. Message Envelope

Messages should contain:

- Message type
- Timestamp
- Correlation ID
- Payload
- Version

Payload structure should follow the event architecture.

---

# 9. Event Streaming

WebSocket messages should primarily represent published domain events.

See:

- 06-event-driven-architecture.md

---

# 10. Heartbeats

The protocol should support:

- Ping
- Pong
- Idle timeout
- Connection health monitoring

---

# 11. Reconnection

Clients should:

- Retry automatically
- Resume subscriptions
- Avoid duplicate processing
- Recover gracefully

---

# 12. Backpressure

Implementations should define strategies for:

- Slow consumers
- Large event bursts
- Queue limits
- Event dropping policies

---

# 13. Error Handling

Errors should include:

- Machine-readable code
- Human-readable description
- Correlation ID
- Recovery guidance (where applicable)

---

# 14. Security

The WebSocket layer should support:

- Authentication
- Authorization
- TLS
- Audit logging
- PHI protection
- Connection limits

---

# 15. Performance Guidance

The implementation should support:

- High-frequency event streams
- Compression
- Efficient serialization
- Minimal latency
- Horizontal scalability

---

# 16. Plugin Integration

Plugins may:

- Publish events
- Subscribe to events
- Define custom channels
- Provide additional notifications

Plugins should not interfere with core protocol behavior.

---

# 17. Monitoring

Expose operational metrics including:

- Active connections
- Messages/sec
- Subscription counts
- Disconnect rates
- Processing latency

---

# 18. Acceptance Criteria

The architecture is complete when:

- Connection lifecycle is defined.
- Subscription model is documented.
- Message envelope is established.
- Security expectations are documented.
- Reconnection strategy is defined.
- Performance guidance is documented.
- Plugin integration points are identified.

---

# 19. References

- 03-system-architecture.md
- 04-technology-stack.md
- 05-system-modules.md
- 06-event-driven-architecture.md
- 07-data-model.md
- 08-rest-api-specification.md
