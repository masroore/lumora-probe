"""FastAPI application and versioned REST API router."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from lumora_probe.core.errors import (
    ConfigurationError,
    LumoraError,
    PathSecurityError,
    RestartRequiredError,
    SettingLockedError,
    VersionMismatchError,
)
from lumora_probe.core.logging import new_correlation_id

from .association_routes import create_association_router
from .capture_routes import create_capture_router
from .contracts import ErrorResponse
from .event_routes import create_event_router
from .operation_routes import OperationRegistry, create_operation_router
from .resources import ResourceStore
from .study_routes import create_projection_routers

API_PREFIX = "/api/v1"


def _http_status_for(error: LumoraError) -> int:
    """Map structured application errors to stable HTTP status classes."""

    if isinstance(error, (SettingLockedError, RestartRequiredError, VersionMismatchError)):
        return 409
    if isinstance(error, (ConfigurationError, PathSecurityError)):
        return 400
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


def create_app(
    *,
    capture_store: ResourceStore | None = None,
    projection_store: ResourceStore | None = None,
    association_store: ResourceStore | None = None,
    event_store: ResourceStore | None = None,
    operation_registry: OperationRegistry | None = None,
) -> FastAPI:
    """Create the Lumora Probe ASGI application."""

    application = FastAPI(
        title="Lumora Probe",
        version="0.1.0",
        description="DICOM observability, troubleshooting, and engineering platform.",
    )
    application.add_exception_handler(LumoraError, lumora_error_handler)
    application.include_router(api_v1_router)
    application.include_router(create_capture_router(capture_store), prefix=API_PREFIX)
    for router in create_projection_routers(projection_store):
        application.include_router(router, prefix=API_PREFIX)
    application.include_router(create_association_router(association_store), prefix=API_PREFIX)
    application.include_router(create_event_router(event_store), prefix=API_PREFIX)
    application.include_router(create_operation_router(operation_registry), prefix=API_PREFIX)
    return application


app = create_app()

__all__: tuple[str, ...] = ()
