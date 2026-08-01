"""Central request security seams for the unauthenticated v1 API."""

from __future__ import annotations

import inspect
import secrets
from collections.abc import Awaitable, Callable, Iterable, Mapping
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from .contracts import ErrorResponse

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ALLOWED_FETCH_SITES = frozenset({"", "none", "same-origin", "same-site"})
SecurityAuditSink = Callable[[str, Mapping[str, object]], Awaitable[None] | None]


class SecurityPolicy:
    """Explicit host, proxy, origin, and read-only policy for one server."""

    def __init__(
        self,
        *,
        read_only: bool = False,
        allowed_hosts: Iterable[str] = ("localhost", "127.0.0.1", "[::1]"),
        trusted_proxies: Iterable[str] = (),
        allowed_origins: Iterable[str] = (),
    ) -> None:
        self.read_only = read_only
        self.allowed_hosts = frozenset(_normalise_host(host) for host in allowed_hosts)
        self.trusted_proxies = frozenset(_normalise_host(host) for host in trusted_proxies)
        self.allowed_origins = frozenset(allowed_origins)

    def update_read_only(self, read_only: bool) -> None:
        """Apply the mutable read-only gate to subsequent requests."""
        self.read_only = bool(read_only)

    def update_allowed_origins(self, origins: Iterable[str]) -> None:
        self.allowed_origins = frozenset(origins)

    def validate_websocket(
        self,
        *,
        host_header: str,
        client_host: str,
        origin: str | None,
        forwarded_host: str | None = None,
    ) -> str | None:
        """Return a handshake failure reason, or ``None`` when it is trusted."""

        effective_host = host_header
        if _normalise_host(client_host) in self.trusted_proxies and forwarded_host:
            effective_host = forwarded_host.split(",", 1)[0].strip()
        host = _host_from_header(effective_host)
        if host not in self.allowed_hosts:
            return "The WebSocket Host is not allowed."
        if (
            origin is not None
            and origin not in self.allowed_origins
            and _origin_host(origin) != host
        ):
            return "The WebSocket Origin is not allowed."
        return None


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply all HTTP trust-boundary checks before route handlers execute."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        policy: SecurityPolicy,
        audit_sink: SecurityAuditSink | None = None,
    ) -> None:
        super().__init__(app)
        self.policy = policy
        self.audit_sink = audit_sink

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        failure = await self._validate(request)
        if failure is not None:
            return failure
        response = await call_next(request)
        for header_name in ("access-control-allow-origin", "Access-Control-Allow-Origin"):
            if header_name in response.headers:
                del response.headers[header_name]
        return response

    async def _validate(self, request: Request) -> JSONResponse | None:
        host = self._effective_host(request)
        if host not in self.policy.allowed_hosts:
            return await self._failure(
                status=400,
                code="LUMORA-WEB-HOST-001",
                message="The request Host is not allowed.",
                remediation="Use a configured local host name or update the host allowlist.",
                context={"host": host},
            )

        if request.method not in _MUTATING_METHODS:
            return None
        if self.policy.read_only:
            return await self._failure(
                status=403,
                code="LUMORA-WEB-READONLY-001",
                message="The server is in read-only mode.",
                remediation="Disable read-only mode before sending a state-changing request.",
                context={"method": request.method, "path": request.url.path},
            )
        origin_failure = await self._validate_origin(request, host)
        return origin_failure

    async def _failure(
        self,
        *,
        status: int,
        code: str,
        message: str,
        remediation: str,
        context: Mapping[str, object],
    ) -> JSONResponse:
        if self.audit_sink is not None:
            result = self.audit_sink(code, context)
            if inspect.isawaitable(result):
                await result
        return _error_response(
            status=status,
            code=code,
            message=message,
            remediation=remediation,
            context=dict(context),
        )

    def _effective_host(self, request: Request) -> str:
        client_host = _normalise_host(request.client.host if request.client else "")
        host_header = request.headers.get("host", "")
        if client_host in self.policy.trusted_proxies:
            forwarded = request.headers.get("x-forwarded-host")
            if forwarded:
                host_header = forwarded.split(",", 1)[0].strip()
        return _host_from_header(host_header)

    async def _validate_origin(self, request: Request, host: str) -> JSONResponse | None:
        fetch_site = request.headers.get("sec-fetch-site", "").casefold()
        if fetch_site not in _ALLOWED_FETCH_SITES:
            return await self._failure(
                status=403,
                code="LUMORA-WEB-ORIGIN-002",
                message="Cross-site state changes are not allowed.",
                remediation="Send the request from the configured application origin.",
                context={"sec_fetch_site": fetch_site},
            )
        origin = request.headers.get("origin")
        if origin is None:
            return None
        if origin in self.policy.allowed_origins or _origin_host(origin) == host:
            return None
        return await self._failure(
            status=403,
            code="LUMORA-WEB-ORIGIN-001",
            message="The request Origin is not allowed.",
            remediation="Use the configured application origin.",
            context={"origin": origin},
        )


def _error_response(
    *, status: int, code: str, message: str, remediation: str, context: dict[str, object]
) -> JSONResponse:
    correlation_id = secrets.token_hex(16)
    error = ErrorResponse(
        status=status,
        code=code,
        message=message,
        remediation=remediation,
        context=context,
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=status,
        content=error.model_dump(mode="json"),
        headers={"X-Correlation-ID": correlation_id},
    )


def _normalise_host(value: str) -> str:
    return value.strip().lower().strip("[]")


def _host_from_header(value: str) -> str:
    """Extract a normalized host from an HTTP Host or forwarded-host value."""
    candidate = value.strip()
    if not candidate:
        return ""
    try:
        parsed = urlsplit(f"//{candidate}")
        hostname = parsed.hostname
    except ValueError:
        hostname = None
    return _normalise_host(hostname or candidate.split(":", 1)[0])


def _origin_host(origin: str) -> str:
    return _normalise_host(urlsplit(origin).hostname or "")


__all__: tuple[str, ...] = ()
