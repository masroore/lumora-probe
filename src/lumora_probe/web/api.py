"""FastAPI application and versioned REST API router."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lumora_probe.core.clock import Clock, SystemClock
from lumora_probe.core.errors import (
    ConfigurationError,
    LumoraError,
    PathSecurityError,
    RestartRequiredError,
    SettingLockedError,
    VersionMismatchError,
)
from lumora_probe.core.ids import IdGenerator, UUIDv7Generator
from lumora_probe.core.logging import new_correlation_id

from .association_routes import create_association_router
from .capture_routes import create_capture_router
from .client_event_routes import ClientEventPublisher, RateLimiter, create_client_event_router
from .contracts import ErrorResponse
from .event_routes import create_event_router
from .health_routes import HealthProvider, create_health_router
from .operation_routes import OperationRegistry, create_operation_router
from .resources import ResourceStore
from .security import SecurityMiddleware, SecurityPolicy
from .settings_routes import SettingsProvider, create_settings_router
from .study_routes import create_projection_routers

API_PREFIX = "/api/v1"


def _http_status_for(error: LumoraError) -> int:
    """Map structured application errors to stable HTTP status classes."""

    if isinstance(error, (SettingLockedError, RestartRequiredError, VersionMismatchError)):
        return 409
    if isinstance(error, (ConfigurationError, PathSecurityError)):
        return 400
    if error.code == "LUMORA-WEB-RATE-001":
        return 429
    if error.code == "LUMORA-WEB-EVENTS-002":
        return 422
    if error.code == "LUMORA-WEB-EVENTS-001":
        return 503
    return 500


api_v1_router = APIRouter(prefix=API_PREFIX, tags=["api-v1"])


@api_v1_router.get("", include_in_schema=False)
def api_root() -> dict[str, str]:
    """Return the stable API version root without exposing mutable state."""

    return {"version": "v1"}


async def lumora_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Return a consistent HTTP response for a structured core error."""

    if not isinstance(error, LumoraError):
        raise error

    correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
    response = ErrorResponse.from_error(
        error,
        correlation_id=correlation_id,
        status=_http_status_for(error),
    )
    return JSONResponse(
        status_code=response.status,
        content=response.model_dump(mode="json"),
        headers={"X-Correlation-ID": response.correlation_id},
    )


async def http_exception_handler(request: Request, error: Exception) -> JSONResponse:
    """Normalize route-level HTTP failures into the public error contract."""

    http_error = cast(HTTPException, error)
    correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
    response = ErrorResponse(
        status=http_error.status_code,
        code=f"LUMORA-WEB-HTTP-{http_error.status_code}",
        message=str(http_error.detail),
        remediation="Correct the request and retry.",
        context={},
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=http_error.status_code,
        content=response.model_dump(mode="json"),
        headers={"X-Correlation-ID": correlation_id},
    )


async def validation_exception_handler(request: Request, error: Exception) -> JSONResponse:
    """Normalize Pydantic request validation failures into the public error contract."""

    validation_error = cast(RequestValidationError, error)
    correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
    response = ErrorResponse(
        status=422,
        code="LUMORA-WEB-VALIDATION-001",
        message="Request validation failed.",
        remediation="Correct the fields listed in context and retry.",
        context={"errors": validation_error.errors()},
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=422,
        content=response.model_dump(mode="json"),
        headers={"X-Correlation-ID": correlation_id},
    )


def create_app(
    *,
    capture_store: ResourceStore | None = None,
    projection_store: ResourceStore | None = None,
    association_store: ResourceStore | None = None,
    event_store: ResourceStore | None = None,
    operation_registry: OperationRegistry | None = None,
    settings_provider: SettingsProvider | None = None,
    health_provider: HealthProvider | None = None,
    security_policy: SecurityPolicy | None = None,
    event_publisher: ClientEventPublisher | None = None,
    event_clock: Clock | None = None,
    event_id_generator: IdGenerator | None = None,
    client_event_rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    """Create the Lumora Probe ASGI application."""

    application = FastAPI(
        title="Lumora Probe",
        version="0.1.0",
        description="DICOM observability, troubleshooting, and engineering platform.",
    )
    application.add_exception_handler(LumoraError, lumora_error_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_middleware(SecurityMiddleware, policy=security_policy or SecurityPolicy())
    application.include_router(api_v1_router)
    application.include_router(create_capture_router(capture_store), prefix=API_PREFIX)
    for router in create_projection_routers(projection_store):
        application.include_router(router, prefix=API_PREFIX)
    application.include_router(create_association_router(association_store), prefix=API_PREFIX)
    application.include_router(create_event_router(event_store), prefix=API_PREFIX)
    application.include_router(create_operation_router(operation_registry), prefix=API_PREFIX)
    application.include_router(create_settings_router(settings_provider), prefix=API_PREFIX)
    application.include_router(create_health_router(health_provider), prefix=API_PREFIX)
    application.include_router(
        create_client_event_router(
            publisher=event_publisher,
            clock=event_clock or SystemClock(),
            id_generator=event_id_generator or UUIDv7Generator(),
            rate_limiter=client_event_rate_limiter,
        ),
        prefix=API_PREFIX,
    )
    return application


app = create_app()

__all__: tuple[str, ...] = ()
