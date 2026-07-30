"""FastAPI application and versioned REST API router."""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Protocol, cast

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from lumora_probe.core.errors import (
    ConfigurationError,
    LumoraError,
    PathSecurityError,
    RestartRequiredError,
    SettingLockedError,
    VersionMismatchError,
)

from .association_routes import create_association_router
from .capture_routes import RetentionStateProvider, create_capture_router
from .client_event_routes import (
    ClientEventPublisher,
    RateLimiter,
    WebEventClock,
    WebIdGenerator,
    create_client_event_router,
)
from .contracts import ErrorResponse
from .event_routes import create_event_router
from .frame_routes import FrameProvider, create_frame_router
from .health_routes import HealthProvider, create_health_router
from .live import (
    CoalescingGovernor,
    LiveEventSource,
    LiveSettings,
    LiveUpdateHub,
    NullEventSource,
    create_live_router,
)
from .metadata_routes import MetadataProvider, create_metadata_router
from .operation_routes import OperationRegistry, create_operation_router
from .resources import ResourceStore
from .security import SecurityMiddleware, SecurityPolicy
from .settings_routes import SettingsProvider, create_settings_router
from .study_routes import (
    StudyBrowserProvider,
    create_projection_routers,
    create_study_browser_router,
)
from .workspace_routes import STATIC_ROOT, WorkspaceData, create_workspace_router

API_PREFIX = "/api/v1"


class CaptureRuntime(Protocol):
    """Lifecycle adapter for the capture engine owned by application bootstrap."""

    ring_buffer: RetentionStateProvider

    async def start(self, *, event_bus: Any | None = None) -> None: ...

    async def stop(self) -> None: ...


class ReplayRuntime(Protocol):
    """Application replay composition hook used by the ASGI lifespan."""

    async def startup(self) -> int: ...


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

    correlation_id = request.headers.get("X-Correlation-ID") or secrets.token_hex(16)
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
    correlation_id = request.headers.get("X-Correlation-ID") or secrets.token_hex(16)
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
    correlation_id = request.headers.get("X-Correlation-ID") or secrets.token_hex(16)
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
    retention_provider: RetentionStateProvider | None = None,
    capture_engine: CaptureRuntime | None = None,
    ring_buffer_service: Any | None = None,
    projection_store: ResourceStore | None = None,
    association_store: ResourceStore | None = None,
    event_store: ResourceStore | None = None,
    operation_registry: OperationRegistry | None = None,
    settings_provider: SettingsProvider | None = None,
    health_provider: HealthProvider | None = None,
    security_policy: SecurityPolicy | None = None,
    event_publisher: ClientEventPublisher | None = None,
    event_clock: WebEventClock | None = None,
    event_id_generator: WebIdGenerator | None = None,
    client_event_rate_limiter: RateLimiter | None = None,
    event_bus: LiveEventSource | None = None,
    live_settings: LiveSettings | None = None,
    replay_runtime: ReplayRuntime | None = None,
    workspace_data: WorkspaceData | None = None,
    frame_provider: FrameProvider | None = None,
    metadata_provider: MetadataProvider | None = None,
    study_browser_provider: StudyBrowserProvider | None = None,
) -> FastAPI:
    """Create the Lumora Probe ASGI application."""

    active_policy = security_policy or SecurityPolicy()
    active_bus = event_bus or NullEventSource()
    active_retention = retention_provider or (
        capture_engine.ring_buffer if capture_engine is not None else None
    )
    active_settings = live_settings or LiveSettings()
    live_governor = CoalescingGovernor(bus=active_bus, settings=active_settings)
    live_hub = LiveUpdateHub(bus=active_bus, governor=live_governor)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
        if replay_runtime is not None:
            await replay_runtime.startup()
        if capture_engine is not None:
            await capture_engine.start(
                event_bus=None if isinstance(active_bus, NullEventSource) else active_bus
            )
        try:
            yield
        finally:
            if capture_engine is not None:
                await capture_engine.stop()
            await live_hub.stop()

    application = FastAPI(
        title="Lumora Probe",
        version="0.1.0",
        description="DICOM observability, troubleshooting, and engineering platform.",
        lifespan=lifespan,
    )
    application.add_exception_handler(LumoraError, lumora_error_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_middleware(SecurityMiddleware, policy=active_policy)
    if STATIC_ROOT.is_dir():
        application.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
    application.include_router(api_v1_router)
    application.include_router(create_workspace_router(data=workspace_data))
    application.include_router(create_frame_router(frame_provider), prefix=API_PREFIX)
    application.include_router(create_metadata_router(metadata_provider), prefix=API_PREFIX)
    application.include_router(
        create_study_browser_router(study_browser_provider), prefix=API_PREFIX
    )
    application.include_router(
        create_capture_router(capture_store, active_retention), prefix=API_PREFIX
    )
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
            clock=event_clock,
            id_generator=event_id_generator,
            rate_limiter=client_event_rate_limiter,
        ),
        prefix=API_PREFIX,
    )
    application.state.event_bus = active_bus
    application.state.live_hub = live_hub
    application.state.replay_runtime = replay_runtime
    application.include_router(
        create_live_router(
            hub=live_hub,
            security_policy=active_policy,
            settings=active_settings,
        )
    )
    if ring_buffer_service is not None:
        from datetime import UTC, datetime

        from .retention import RingBufferRetentionMap

        class _DateTimeClock:
            def now(self) -> datetime:
                return datetime.now(UTC)

        application.state.retention_map = RingBufferRetentionMap(
            ring_buffer_service, _DateTimeClock()
        )
    return application


app = create_app()

__all__: tuple[str, ...] = ()
