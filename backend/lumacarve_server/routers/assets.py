"""Opaque asset IDs, image-only upload, bounded streaming."""
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..assets import AssetError, locate_asset, store_asset

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.post("", status_code=201)
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        return (await store_asset(file, request.app.state.settings)).json()
    except AssetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{asset_id}")
def get_image(request: Request, asset_id: str):
    try:
        path = locate_asset(request.app.state.settings, asset_id)
    except AssetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    type_ = "image/jpeg" if path.suffix == ".jpg" else f"image/{path.suffix.lstrip('.')}"
    return FileResponse(path, media_type=type_, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
