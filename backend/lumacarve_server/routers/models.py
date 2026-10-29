"""Read-only local model index; no automatic download or code loading."""
from fastapi import APIRouter, Request

from ..models import KNOWN_FAMILIES, scan_models

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
def models(request: Request):
    root = request.app.state.settings.models_dir
    return {
        "files": [model.__dict__ if hasattr(model, "__dict__") else {
            "id": model.id,
            "category": model.category,
            "name": model.name,
            "relative_path": model.relative_path,
            "size_bytes": model.size_bytes,
        } for model in scan_models(root)],
        "planned_families": list(KNOWN_FAMILIES),
        "loaded": [],
        "backend_ready": False,
    }
