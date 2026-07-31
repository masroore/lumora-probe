# Security Review

## 1. Trust Boundary and Network Exposure

### 1.1 Loopback-by-default and the network gate

`StartupConfig.bind_host` defaults to `"127.0.0.1"`. Any non-loopback bind requires
`allow_unauthenticated_network=True` explicitly set, enforced by `_validate_network_gate()` at
startup. This is the correct design for a tool with no authentication layer.

`DICOMListenerConfig.port` validates `1024 <= port <= 65535` (non-privileged ports only). The
default is 11112 — consistent with the specification's intent to never require root.

### 1.2 SecurityMiddleware

`SecurityMiddleware` enforces:

1. **Host allowlist** — every request must have a `Host` header matching a configured set.
   Default allows `localhost`, `127.0.0.1`, `[::1]`. Non-matching hosts return 400.
2. **Read-only mode** — mutating methods (POST/PUT/PATCH/DELETE) are rejected with 403 if
   `read_only=True`.
3. **Origin/Sec-Fetch-Site for state-changing requests** — CSRF protection via two complementary
   checks:
   - `Sec-Fetch-Site` must be in `{same-origin, same-site, none, ""}`. Cross-site requests
     are rejected with 403.
   - If `Origin` header is present, it must match the host or the configured allowlist.

This is a correct and complete CSRF mitigation for a loopback tool. The `Sec-Fetch-Site` check
is a modern browser-enforced signal; the `Origin` fallback handles older browsers and non-browser
clients.

**One gap:** The `Sec-Fetch-Site` check only applies to mutating methods (the early return for
GET/HEAD/OPTIONS before the check):

```python
if request.method not in _MUTATING_METHODS:
    return None
```

Non-mutating requests with a cross-site origin pass without any check. This is correct by design
(GET requests should not mutate state), but means an attacker can use cross-origin GET requests
to probe the API surface. For a loopback tool this is acceptable; on a non-loopback deployment
it means metadata leakage is possible via CORS.

### 1.3 CORS headers stripped

```python
for header_name in ("access-control-allow-origin", "Access-Control-Allow-Origin"):
    if header_name in response.headers:
        del response.headers[header_name]
```

The middleware actively strips any `Access-Control-Allow-Origin` header from responses. This
prevents any route handler from accidentally adding a wildcard CORS header. Correct and defensive.

### 1.4 Security audit trail

Every security failure is routed through the `audit_sink` passed to `SecurityMiddleware`.
In `bootstrap.py` this writes to `AuditLog` in `app.db`. Security refusals are therefore
durable and auditable. This is a strength.

---

## 2. Path Traversal

### 2.1 `assert_contained()` — correct

Resolves symlinks before the containment check. A symlink outside the allowed root will be
detected. See correctness review §8 for detail.

### 2.2 `unpack_capture()` — correct

Checks every zip member with `assert_contained()` before extraction. Symlink entries rejected.
`member.filename` paths are not sanitized before the check, but `assert_contained` handles
traversal via `relative_to()` after resolving. Correct.

### 2.3 `ContentAddressedObjectStore.path_for()` — correct

Validates digest format (64 lowercase hex chars) before constructing the path. `assert_contained`
called on the resulting path. Correct.

---

## 3. Input Validation

### 3.1 AETitle allows leading/trailing whitespace in the encoded value

```python
if not self.value.strip() or any(ord(character) < 0x20 for character in self.value):
    raise domain_invariant(...)
```

The invariant rejects values that are *entirely* whitespace, but allows values that contain
internal spaces (e.g., `"SCU A"`) or have leading/trailing spaces (e.g., `" SCU"`). DICOM AE
titles are padded with spaces to 16 bytes in the DICOM standard, but an AE title that starts or
ends with a space is technically valid per DICOM, so this is not an error. However, when
displayed, `" SCU"` and `"SCU"` look identical, which could mislead operators.

**Severity:** Informational.

### 3.2 DICOM UID does not normalize leading zeros in components

```python
or any(len(component) > 1 and component.startswith("0") for component in components)
```

The validator correctly rejects UIDs with leading zeros in multi-digit components. Correct per
DICOM PS3.5 §9.1.

### 3.3 `bind_host` validation allows hostnames without format checking

```python
try:
    ipaddress.ip_address(candidate)
except ValueError:
    if any(character.isspace() for character in candidate):
        raise ValueError("must be an IP address or hostname") from None
```

If `bind_host` is not a valid IP address and contains no whitespace, it is accepted as a
hostname without any further validation (no RFC 1123 hostname check, no length check). An
operator who misconfigs `bind_host = "my host"` gets a whitespace-rejection error; but
`bind_host = "my_host!!!"` would be accepted at config validation time and fail later at bind.

**Severity:** Low (config error, not a security bypass).

---

## 4. WebSocket Security

`SecurityPolicy.validate_websocket()` performs:
1. Host header validation with optional proxy forwarding.
2. Origin header validation against the host or an allowlist.

This is the same model as the HTTP middleware. The WebSocket upgrade is rejected at the ASGI
layer before the handler runs. The implementation is correct.

---

## 5. Client-Asserted Events

The bus rejects client-asserted events that are not registered Viewer events produced by
`"web-ui"`. This is the correct quarantine: a user-controlled browser cannot inject fake
`CaptureStarted` or `AssociationAccepted` events that would influence analysis or replay.

The quarantine is enforced at publish time on the loop, not at the API boundary. This means
even if the API route handler fails to set `origin=CLIENT_ASSERTED`, the event category check
would catch an attempt to publish a non-Viewer event from the web-ui producer. There is no
corresponding check for non-web-ui producers attempting to assert Viewer events — but in
production, all producers on the loop are internal, not user-controlled.

---

## 6. SQL Injection

All SQL queries use parameterized form (`?` placeholders). No string interpolation of
user-controlled values into SQL strings was found in any reviewed file.

---

## 7. Sensitive Data Handling

`LumoraError.as_dict()` serializes the `context` field, which can contain user-provided values
(file paths, config keys). These are returned in API error responses. For a loopback tool this
is acceptable; it aids debugging. If the tool is ever deployed non-locally, path information in
error responses could aid reconnaissance.

The `AuditLog.append()` uses `json.dumps(..., default=str)` for payloads. This means any
non-JSON-serializable object is stringified, which could inadvertently serialize sensitive
objects. The `default=str` fallback is a convenience trade-off; it is correct for the current
use cases (datetime objects, pathlib.Path).

---

## 8. Redaction

The reports/redaction module is present but was not fully read. Based on `CLAUDE.md`:
*"Never claim anonymization, de-identification, or PS3.15 compliance. Redaction is honest and
partial; object-dropping is the default handover."*

The redaction implementation is explicitly partial by design, which is correctly documented.
No false compliance claims were observed in the reviewed code.

---

## 9. Summary

| Category | Status | Notes |
|---|---|---|
| Network exposure gate | ✅ Correct | Non-loopback requires explicit acknowledgment |
| Host allowlist | ✅ Correct | Default restricts to loopback |
| CSRF (Sec-Fetch-Site + Origin) | ✅ Correct | Both checks present on mutating methods |
| CORS header stripping | ✅ Correct | Active removal from all responses |
| Path traversal (HTTP) | ✅ Correct | assert_contained everywhere |
| Zip-slip (lpcap unpack) | ✅ Correct | assert_contained on every member |
| SQL injection | ✅ Correct | All queries parameterized |
| Client-asserted event quarantine | ✅ Correct | Fail-closed at publish time |
| Security audit trail | ✅ Correct | Durable per-event in app.db |
| AE title whitespace | ℹ️ Info | Technically valid; cosmetically misleading |
| bind_host hostname validation | ℹ️ Info | Non-IP hostnames accepted without format check |
| Error context in API responses | ℹ️ Info | Acceptable for loopback; revisit for non-local |
