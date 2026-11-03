"""Real dataset CRUD. No background GPU work or arbitrary filesystem paths."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..datasets import DatasetConflict, DatasetError, DatasetNotFound

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


class NewDataset(BaseModel):
    id: str = Field(min_length=1, max_length=48)
    title: str = Field(min_length=1, max_length=80)


class CaptionUpdate(BaseModel):
    caption: str = Field(max_length=20_000)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, DatasetNotFound):
        return HTTPException(404, detail="Dataset or image not found")
    if isinstance(exc, DatasetConflict):
        return HTTPException(409, detail=str(exc))
    return HTTPException(422, detail=str(exc))


@router.get("")
def list_datasets(request: Request):
    return {"datasets": request.app.state.datasets.list_datasets()}


@router.post("", status_code=201)
def create_dataset(request: Request, data: NewDataset):
    try:
        return request.app.state.datasets.create_dataset(data.id, data.title)
    except (DatasetError, DatasetConflict) as exc:
        raise _error(exc) from exc


@router.get("/{dataset_id}/images")
def list_images(request: Request, dataset_id: str, limit: int = 48, offset: int = 0):
    try:
        return request.app.state.datasets.list_items(dataset_id, limit=limit, offset=offset)
    except (DatasetError, DatasetNotFound) as exc:
        raise _error(exc) from exc


@router.post("/{dataset_id}/images", status_code=201)
async def import_image(request: Request, dataset_id: str, file: UploadFile = File(...), caption: str = Form(default="")):
    try:
        return await request.app.state.datasets.import_image(dataset_id, file, caption)
    except (DatasetError, DatasetNotFound, DatasetConflict) as exc:
        raise _error(exc) from exc


@router.get("/{dataset_id}/images/{item_id}")
def serve_image(request: Request, dataset_id: str, item_id: str):
    try:
        path, media_type = request.app.state.datasets.image_path(dataset_id, item_id)
    except (DatasetError, DatasetNotFound) as exc:
        raise _error(exc) from exc
    return FileResponse(path, media_type=media_type, headers={
        "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
    })


@router.put("/{dataset_id}/images/{item_id}/caption")
def edit_caption(request: Request, dataset_id: str, item_id: str, data: CaptionUpdate):
    try:
        return request.app.state.datasets.update_caption(dataset_id, item_id, data.caption)
    except (DatasetError, DatasetNotFound) as exc:
        raise _error(exc) from exc


@router.delete("/{dataset_id}/images/{item_id}", status_code=204)
def delete_image(request: Request, dataset_id: str, item_id: str):
    try:
        request.app.state.datasets.delete_item(dataset_id, item_id)
    except (DatasetError, DatasetNotFound) as exc:
        raise _error(exc) from exc
    return Response(status_code=204)
