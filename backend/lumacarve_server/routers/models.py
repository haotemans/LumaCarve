"""Read-only local model index; no automatic download or code loading."""
from fastapi import APIRouter, HTTPException, Request
from ..jobs import EngineUnavailable

from ..models import KNOWN_FAMILIES, scan_models
from ..adapters.anima import find_anima_snapshot

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
def models(request: Request):
    settings = request.app.state.settings
    root = settings.models_dir
    snapshot = find_anima_snapshot(settings)
    if snapshot is None:
        snapshot_name = None
    else:
        try:
            snapshot_name = snapshot.relative_to(root.resolve()).as_posix()
        except ValueError:
            snapshot_name = str(snapshot)
    return {
        "residency": request.app.state.job_queue.residency(),
        "files": [model.__dict__ if hasattr(model, "__dict__") else {
            "id": model.id,
            "category": model.category,
            "name": model.name,
            "relative_path": model.relative_path,
            "size_bytes": model.size_bytes,
        } for model in scan_models(root)],
        "planned_families": list(KNOWN_FAMILIES),
        "loaded": [request.app.state.job_queue.residency()["model_id"]] if request.app.state.job_queue.residency()["state"] == "loaded" else [],
        "backend_ready": bool(request.app.state.job_queue.adapter.ready),
        "anima_snapshot": snapshot_name,
        "backend_configured": settings.inference_backend == "anima",
    }


@router.post("/unload")
def unload_model(request: Request):
    try:
        return request.app.state.job_queue.unload_idle_model()
    except EngineUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
