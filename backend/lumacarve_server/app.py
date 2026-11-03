"""FastAPI bootstrap. GPU libraries are deliberately absent from import path."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from lumacarve_runtime.rust_bridge import scheduler_backend
from .model_downloads import ModelDownloadManager
from .routers.downloads import router as downloads_router
from .routers.outputs import router as outputs_router
from .jobs import DisabledInference, JobQueue, JobStore

def make_inference_adapter(settings: Settings):
    if settings.inference_backend == "anima":
        from .adapters.anima import AnimaAdapter
        return AnimaAdapter(settings)
    return DisabledInference()

from .routers.jobs import router as jobs_router
from .routers.workflows import router as workflow_router
from .routers.models import router as models_router
from .routers.assets import router as assets_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        queue = JobQueue(JobStore(settings.database_path), make_inference_adapter(settings), settings.max_pending_jobs)
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
    api.include_router(outputs_router)

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
            "engine": (
                settings.inference_backend
                if api.state.job_queue.adapter.ready else "not_connected"
            ),
            "configured_engine": settings.inference_backend,
            # A GPU probe is deliberately not executed by the HTTP API.
            # "Unknown" is distinct from "not available".
            "gpu": {"available": None, "measured": False},
            "policy": "no_model_loaded_on_api_startup",
            "mode": "local_only",
            "inference_offload": settings.inference_offload,
            "memory_planner": {
                # Diffusers automatic CPU offload is NOT the planned AMEP
                # predictive residency/scheduling implementation.
                "adaptive": "not_implemented",
                "current": settings.inference_offload,
            },
            "optimization": {
                # These are CONFIGURATION values, not evidence that a Triton
                # kernel has been loaded, used, benchmarked or accepted.
                "state": "configured_only",
                "validated_on_gpu": False,
                "anima": {
                    "adaln": settings.anima_triton,
                    "rope": settings.anima_triton_rope,
                    "residual": settings.anima_triton_residual,
                    "ffn": settings.anima_triton_ffn,
                },
            },
            "graph_scheduler": scheduler_backend(),
            "queue_scheduler": api.state.job_queue.queue_backend,
            "queue_scheduler_error": api.state.job_queue.fatal_error,
        }

    return api


app = create_app()
