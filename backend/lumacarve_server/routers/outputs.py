"""Read Anima-generated PNGs by opaque output ID; no arbitrary path reads."""
from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/outputs", tags=["outputs"])
OUTPUT_ID = re.compile(r"^[0-9a-f]{32}$")


@router.get("/{output_id}")
def output_image(request: Request, output_id: str):
    if OUTPUT_ID.fullmatch(output_id) is None:
        raise HTTPException(422, detail="Output ID must be a 32-character hex token")
    path = request.app.state.settings.outputs_dir / (output_id + ".png")
    if not path.is_file():
        raise HTTPException(404, detail="Output image not found")
    return FileResponse(
        path, media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
