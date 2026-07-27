# ADR-0010: Loopback by Default; Network Exposure Requires Explicit Acknowledgment

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

ADR-0009 removed authentication and made reverse-proxy deployment first-class. Those
two cannot both hold at the default: inside a container the application **must** bind
`0.0.0.0` or the proxy on the other side of the container boundary cannot reach it. So
shipping a Docker image makes the default deployment an unauthenticated service on all
interfaces with a PHI ring buffer (ADR-0008) behind it — and whether a proxy is
actually in front is invisible to the application.

## Decision

Bind `127.0.0.1` by default. A **non-loopback bind requires explicit acknowledgment**
(`allow_unauthenticated_network = true` / `--trust-network`); without it the server
refuses to start and explains why. No authentication code is introduced — this is an
informed opt-in, not a credential.

The Docker image ships with the flag set, and its documentation states plainly that the
reverse proxy is the security boundary.

**Mitigations for the known attack class**, none of which require auth:

- **Host header allowlist** (`localhost`, `127.0.0.1`, configured hostnames), rejecting
  otherwise. Any page the user visits can issue requests to `localhost:8000`, and DNS
  rebinding defeats same-origin policy.
- **No `Access-Control-Allow-Origin`, ever.**
- **`Origin` / `Sec-Fetch-Site` checks** on state-changing requests **and on the
  WebSocket handshake**. Without the WS check a hostile page can subscribe to the live
  event stream and read PHI as it arrives.
- **Forwarded headers trusted only from a configured trusted-proxy list, empty by
  default.** Otherwise every audit log entry carries an attacker-supplied client
  address.

## Alternatives Considered

- **Loopback default, Docker overrides via config, no acknowledgment.** Rejected: the
  failure is silent, which `03` §12 prohibits.
- **Bind `0.0.0.0` by default with a startup warning.** Rejected: makes the unsafe case
  the default for everyone, including the laptop user.

## References

`03` §12 · `09` §5 · `12` §10, §12 · ADR-0008 · ADR-0009
