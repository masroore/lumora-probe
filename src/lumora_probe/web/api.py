"""FastAPI application and versioned REST API router."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

API_PREFIX = "/api/v1"

api_v1_router = APIRouter(prefix=API_PREFIX, tags=["api-v1"])


@api_v1_router.get("", include_in_schema=False)
def api_root() -> dict[str, str]:
    """Return the stable API version root without exposing mutable state."""

    return {"version": "v1"}


def create_app() -> FastAPI:
    """Create the Lumora Probe ASGI application."""

    application = FastAPI(
        title="Lumora Probe",
        version="0.1.0",
        description="DICOM observability, troubleshooting, and engineering platform.",
    )
    application.include_router(api_v1_router)
    return application


app = create_app()

__all__: tuple[str, ...] = ()
