"""Job API: validation first, then single-GPU-worker admission."""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Literal
from pydantic import BaseModel, Field

from ..assets import AssetError, locate_asset
from ..jobs import EngineUnavailable, JobNotFound, QueueFull
from ..workflows import WorkflowValidationError, validate_workflow

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class JobRequest(BaseModel):
    workflow: dict = Field(...)
    asset_ids: list[str] = Field(default_factory=list, max_length=10)
    mask_asset_id: str | None = None
    priority: Literal['interactive', 'normal', 'background'] = 'interactive'


@router.post("", status_code=202)
def submit(request: Request, payload: JobRequest):
    try:
        summary = validate_workflow(payload.workflow)
    except WorkflowValidationError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    adapter = request.app.state.job_queue.adapter
    # The old UI could enumerate a local browser folder and place its name in
    # model.checkpoint, but that folder was never uploaded to the GPU worker.
    # Reject such paths instead of silently generating with a different model.
    if summary.model_id == "anima-base-1":
        from ..adapters.anima import find_anima_snapshot
        snapshot = find_anima_snapshot(request.app.state.settings)
        for node in payload.workflow["nodes"]:
            if node.get("kind") != "model":
                continue
            chosen = node.get("params", {}).get("checkpoint", "")
            if not chosen:
                break
            root = request.app.state.settings.models_dir.resolve()
            if snapshot is None:
                raise HTTPException(422, detail="Anima snapshot is not installed on this backend")
            try:
                expected = snapshot.relative_to(root).as_posix()
            except ValueError:
                expected = str(snapshot)
            if chosen != expected:
                raise HTTPException(422, detail="Selected checkpoint is not the installed Anima ModularPipeline snapshot")
    if getattr(adapter, "model_id", None) is not None:
        if summary.model_id != adapter.model_id or summary.intent != "create":
            raise HTTPException(
                422, detail=f"Configured {adapter.model_id} backend currently supports text-to-image only"
            )
    if summary.references_required and not payload.asset_ids:
        raise HTTPException(422, detail="Reference editing requires uploaded reference images")
    if summary.mask_required and not payload.mask_asset_id:
        raise HTTPException(422, detail="Inpainting requires uploaded PNG mask")
    if not summary.references_required and payload.asset_ids:
        raise HTTPException(422, detail="Creation workflow does not accept reference images")
    for asset_id in [*payload.asset_ids, *([payload.mask_asset_id] if payload.mask_asset_id else [])]:
        try:
            path = locate_asset(request.app.state.settings, asset_id)
        except (AssetError, FileNotFoundError) as exc:
            raise HTTPException(422, detail=f"Unknown asset: {asset_id}") from exc
        if asset_id == payload.mask_asset_id and path.suffix != ".png":
            raise HTTPException(422, detail="Mask must be a PNG asset")
    try:
        return request.app.state.job_queue.submit(
            payload.workflow, {"asset_ids": payload.asset_ids, "mask_asset_id": payload.mask_asset_id},
            priority=payload.priority,
        )
    except EngineUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    except QueueFull as exc:
        raise HTTPException(429, detail=str(exc)) from exc


@router.get("")
def list_jobs(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    state: Literal["queued", "running", "completed", "failed", "cancelled"] | None = None,
):
    store = request.app.state.job_queue.store
    counts = store.counts()
    return {
        "jobs": store.list(limit=limit, offset=offset, state=state),
        "total": counts[state] if state else sum(counts.values()),
        "counts": counts,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{job_id}")
def get_job(request: Request, job_id: str):
    try:
        return request.app.state.job_queue.store.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(404, detail="Job not found") from exc


@router.post("/{job_id}/cancel")
def cancel_job(request: Request, job_id: str):
    try:
        return request.app.state.job_queue.cancel(job_id)
    except JobNotFound as exc:
        raise HTTPException(404, detail="Job not found") from exc
