"""FastAPI bootstrap. GPU libraries are deliberately absent from import path."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .model_downloads import ModelDownloadManager
from .routers.downloads import router as downloads_router
from .jobs import DisabledInference, JobQueue, JobStore
from .routers.jobs import router as jobs_router
from .routers.workflows import router as workflow_router
from .routers.models import router as models_router
from .routers.assets import router as assets_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        queue = JobQueue(JobStore(settings.database_path), DisabledInference(), settings.max_pending_jobs)
        app.state.job_queue = queue
        queue.start()
        try:
            yield
        finally:
            queue.close()

    api = FastAPI(
        title="LumaCarve Local API",
        version="0.1.0",
        description="Local-first image studio backend. GPU inference is optional and never implied by health.",
        lifespan=lifespan,
    )
    api.state.settings = settings
    api.state.model_downloads = ModelDownloadManager(settings)
    api.include_router(workflow_router)
    api.include_router(models_router)
    api.include_router(assets_router)
    api.include_router(jobs_router)
    api.include_router(downloads_router)

    # CORS is not CSRF protection. Reject disallowed Origins even on simple
    # multipart POST requests, before routes read or persist any data.
    @api.middleware("http")
    async def require_local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        return await call_next(request)

    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    # Bind to loopback by default and reject DNS rebinding via the Host header.
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @api.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "lumacarve", "version": "0.1.0"}

    @api.get("/api/v1/runtime")
    def runtime() -> dict[str, object]:
        return {
            "engine": "not_connected",
            "gpu": {"available": False, "measured": False},
            "policy": "no_model_loaded_on_api_startup",
            "mode": "local_only",
            "inference_offload": settings.inference_offload,
        }

    return api


app = create_app()
