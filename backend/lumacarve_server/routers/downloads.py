"""Optional user-initiated model downloads from trusted catalog."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..model_downloads import ModelDownloadError

router = APIRouter(prefix="/api/v1/downloads", tags=["model downloads"])


class DownloadRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=100)
    revision: str = Field(default="master", max_length=91)
    provider: str | None = Field(default=None, pattern=r"^(modelscope|huggingface)$")


@router.get("/catalog")
def catalog(request: Request):
    manager = request.app.state.model_downloads
    return {"region": manager.settings.resolved_download_region, "downloads_enabled": manager.settings.allow_model_download, "models": manager.catalog()}


@router.post("", status_code=202)
def start(request: Request, payload: DownloadRequest):
    try:
        return request.app.state.model_downloads.submit(payload.model_id, payload.revision, provider=payload.provider)
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(429, detail=str(exc)) from exc
    except ModelDownloadError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.get("/{job_id}")
def status(request: Request, job_id: str):
    try:
        return request.app.state.model_downloads.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, detail="Download task not found") from exc
